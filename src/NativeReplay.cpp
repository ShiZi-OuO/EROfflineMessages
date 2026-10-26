// ER 2.7.2.0-only native replay. No save access, sockets or official capture code.
#include "MessagePack.h"
#include "RuntimeSupport.h"
#include "SpatialIndex.h"
#include "CacheBudget.h"
#include <MinHook.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <numeric>
#include <memory>
#include <unordered_map>

namespace {
HMODULE self{};uintptr_t base{};er::LogFile logFile;
HANDLE processInstance{};
using Update=void(*)(void*,float);
using Receive=void(*)(void*,const void*,const void*);
using Register=void*(*)(void*,void*,bool);
using Neutral=void*(*)(void*);
using Validate=bool(*)(void*,const void*);
Update originalUpdate{};Register originalRegister{};Receive receive{};Neutral neutral{};Validate validate{};
er::MessagePack pack;
std::unique_ptr<er::SpatialIndex> spatial;
std::unordered_map<uint64_t,size_t> packIds;
std::atomic<bool> disabled{},paused{},workerSafe{};
std::atomic<uint64_t> ticks{},microseconds{},maximumMicros{},sceneGeneration{},registrations{},rebindings{},repairs{};
thread_local bool localReceive{};
thread_local size_t localIndex{};
thread_local uintptr_t localResult{};
DWORD updateThread{};
struct Scene{uintptr_t db{},head{},manager1{},manager2{};uint32_t map{};bool operator==(const Scene&)const=default;}scene;
std::vector<size_t> indices;
std::vector<size_t> nearbyIndices;
std::vector<uint8_t> present;
std::vector<uint8_t> bound;
std::vector<uintptr_t> cached;
std::unordered_map<uint64_t,size_t> localIds;
std::atomic<unsigned> nativeItems{},cachedLocal{},boundLocal{};
struct WorkCounters{std::atomic<uint64_t> calls{},sum{},maximum{};};
std::array<WorkCounters,3> workTimes; // registration, maintenance, missing-cache repair
struct WorkSample{
    unsigned phase;LARGE_INTEGER start{};
    explicit WorkSample(unsigned p):phase(p){QueryPerformanceCounter(&start);}
    ~WorkSample(){LARGE_INTEGER end{},frequency{};QueryPerformanceCounter(&end);QueryPerformanceFrequency(&frequency);
        const auto us=static_cast<uint64_t>((end.QuadPart-start.QuadPart)*1000000/frequency.QuadPart);
        auto& c=workTimes[phase];c.calls.fetch_add(1,std::memory_order_relaxed);c.sum.fetch_add(us,std::memory_order_relaxed);
        auto previous=c.maximum.load(std::memory_order_relaxed);while(us>previous&&!c.maximum.compare_exchange_weak(previous,us,std::memory_order_relaxed)){}
    }
};
size_t cursor{};unsigned stable{},spacing{},attempts{},failureStreak{};
ULONGLONG nextMaintenance{},registrationRetryAfter{};bool complete{},repairOnly{},budgetWaiting{};
ULONGLONG nextSelection{};
bool selectionReady{};
std::array<float,3> selectionPosition{};
alignas(16) std::array<uint8_t,er::PayloadSize> payload{};
const std::array<uintptr_t,3> emptyGroups{};

void Fail(const std::string& reason){if(!disabled.exchange(true))logFile.Write("Disabled",reason);}
bool Signature(uintptr_t rva,std::initializer_list<uint8_t> expected){
    std::array<uint8_t,64> bytes{};SIZE_T n{};
    return ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(base+rva),bytes.data(),expected.size(),&n)
      &&n==expected.size()&&std::equal(expected.begin(),expected.end(),bytes.begin());
}
bool Current(void* instance,Scene& current)noexcept{
    uintptr_t net{},type{};uint32_t map{};
    if(!workerSafe.load(std::memory_order_relaxed)||!er::Offline(base)||!er::Read(base+er::NetSlot,net)||!er::Read(net,type)||type!=base+er::NetVft
      ||!er::Read(net+0x1c,map)||map==UINT32_MAX||!er::Read(net+0x78,current.db)||current.db!=reinterpret_cast<uintptr_t>(instance)
      ||!er::Read(current.db,type)||type!=base+er::DbVft||!er::Read(current.db+0x10,current.head)||!current.head
      ||!er::Read(current.db+0x60,current.manager1)||!current.manager1||!er::Read(current.db+0x68,current.manager2)||!current.manager2)return false;
    current.map=map;return true;
}
bool Match(uintptr_t item,const er::Message& expected)noexcept{
    uintptr_t type{};std::array<uint8_t,0x38> fields{};uint32_t map{},sender{};uint64_t key{};std::array<float,3> position{};uint16_t text{},word{};
    if(!er::Read(item,type)||type!=base+er::ItemVft||!er::Read(item+0x14,fields))return false;
    std::memcpy(&map,fields.data(),4);std::memcpy(position.data(),fields.data()+8,12);
    std::memcpy(&text,fields.data()+0x18,2);std::memcpy(&word,fields.data()+0x1c,2);std::memcpy(&key,fields.data()+0x2c,8);
    return key==expected.id&&map==expected.map&&position==expected.position&&text==expected.template1&&word==expected.word1
      &&er::Read(item+8,sender)&&sender==0x7e000001;
}
bool InList(uintptr_t db,uintptr_t item)noexcept{
    uintptr_t head{},node{};if(!item||!er::Read(db+0x10,head)||!head||!er::Read(head,node))return false;
    for(unsigned n=0;node!=head&&n<256;++n){std::array<uintptr_t,3> links{};if(!er::Read(node,links))return false;if(links[2]==item)return true;node=links[0];}
    return false;
}
bool Snapshot(unsigned& count)noexcept{
    std::fill(present.begin(),present.end(),uint8_t{});std::fill(bound.begin(),bound.end(),uint8_t{});std::fill(cached.begin(),cached.end(),uintptr_t{});
    uintptr_t node{},previous=scene.head;count=0;if(!er::Read(scene.head,node))return false;
    while(node!=scene.head&&count<256){
        std::array<uintptr_t,3> links{};uintptr_t type{};uint64_t key{};uint32_t flags{};
        if(!er::Read(node,links)||links[1]!=previous||!links[2]||!er::Read(links[2],type)||type!=base+er::ItemVft||!er::Read(links[2]+0x40,key))return false;
        auto found=localIds.find(key);
        if(found!=localIds.end()){
            const auto slot=found->second;
            if(cached[slot]||!Match(links[2],pack.messages[indices[slot]])||!er::Read(links[2]+0x224,flags))return false;
            // Native admission at 1ba187..1ba1e6 can refuse dense placements.
            // That is a cached record, not a missing record to resubmit every second.
            present[slot]=1;bound[slot]=(flags&8)!=0;cached[slot]=links[2];
        }
        previous=node;node=links[0];++count;
    }
    uintptr_t tail{};const bool valid=node==scene.head&&er::Read(scene.head+8,tail)&&tail==previous;
    if(valid){nativeItems=count;cachedLocal=static_cast<unsigned>(std::count(present.begin(),present.end(),uint8_t{1}));boundLocal=static_cast<unsigned>(std::count(bound.begin(),bound.end(),uint8_t{1}));}
    return valid;
}
void Reset(){scene={};indices.clear();nearbyIndices.clear();present.clear();bound.clear();cached.clear();localIds.clear();cursor=0;stable=0;spacing=0;attempts=0;complete=false;repairOnly=false;budgetWaiting=false;registrationRetryAfter=0;nextMaintenance=0;nextSelection=0;selectionReady=false;nativeItems=0;cachedLocal=0;boundLocal=0;}
bool BlockPosition(std::array<float,3>& position)noexcept{
    uintptr_t world{},player{},owner{},controller{},physics{};
    std::array<float,3> origin{},havok{};
    if(!er::Read(base+0x3d6d018,world)||!er::Read(world+0x1e508,player)
      ||!er::Read(player+0x58,owner)||!er::Read(owner+0x10,controller)
      ||!er::Read(controller+0x190,owner)||!er::Read(owner+0x68,physics)
      ||!er::Read(physics+0x70,havok)||!er::Read(player+0x80,origin))return false;
    for(unsigned i=0;i<3;++i){position[i]=havok[i]-origin[i];if(!std::isfinite(position[i])||std::abs(position[i])>1000000)return false;}
    Scene check{};return Current(reinterpret_cast<void*>(scene.db),check)&&check==scene;
}
bool BudgetResidents(std::vector<er::CacheResident>& residents,uint32_t& capacity){
    if(!er::Read(scene.db+0x20,capacity)||capacity<96||capacity>192)return false;
    uintptr_t node{},previous=scene.head;if(!er::Read(scene.head,node))return false;
    while(node!=scene.head&&residents.size()<256){
        std::array<uintptr_t,3> links{};uintptr_t type{};uint64_t key{};uint32_t flags{};
        if(!er::Read(node,links)||links[1]!=previous||!links[2]||!er::Read(links[2],type)
          ||type!=base+er::ItemVft||!er::Read(links[2]+0x40,key)||!er::Read(links[2]+0x224,flags))return false;
        er::CacheResident resident;auto found=packIds.find(key);
        if(found!=packIds.end()){
            if(!Match(links[2],pack.messages[found->second]))return false;
            resident.record=found->second;
            resident.protectedFromRetirement=(flags&0x1b)!=0;
        }
        residents.push_back(resident);previous=node;node=links[0];
    }
    uintptr_t tail{};return node==scene.head&&er::Read(scene.head+8,tail)&&tail==previous;
}
bool SelectNearby(ULONGLONG now){
    if(now<nextSelection)return selectionReady;
    nextSelection=now+1000;
    std::array<float,3> position{};if(!BlockPosition(position)){selectionReady=false;return false;}
    double movement{};for(unsigned k=0;k<3;++k){const double d=position[k]-selectionPosition[k];movement+=d*d;}
    size_t visited{};bool exhausted{};
    if(!selectionReady||movement>=16.0*16.0){
        const auto result=spatial->Nearby(scene.map,position,250,96,2048);
        nearbyIndices=result.indices;visited=result.visited;exhausted=result.budgetExhausted;
        selectionPosition=position;
    }
    selectionReady=true;
    std::vector<er::CacheResident> residents;residents.reserve(256);uint32_t capacity{};
    if(!BudgetResidents(residents,capacity)){Fail("Selection cache budget invariant failed");return false;}
    auto selected=nearbyIndices;
    selected.resize(er::CachePrefix(selected,residents,capacity));
    if(selected==indices)return true;
    indices=std::move(selected);present.assign(indices.size(),0);bound.assign(indices.size(),0);cached.assign(indices.size(),0);
    localIds.clear();for(size_t i=0;i<indices.size();++i)localIds.emplace(pack.messages[indices[i]].id,i);
    cursor=0;spacing=0;attempts=0;complete=false;repairOnly=false;registrationRetryAfter=0;
    logFile.Write("Selection","map="+std::to_string(scene.map)+" selected="+std::to_string(indices.size())+" candidates="+std::to_string(nearbyIndices.size())+" residents="+std::to_string(residents.size())+" capacity="+std::to_string(capacity)+" visited="+std::to_string(visited)+" exhausted="+std::to_string(exhausted));
    return true;
}
bool RetireUnselected()noexcept{
    // 1c3c70 returns true for flag 4 only when none of 0x19 is set.
    // 1be980 then destroys the item and unlinks it through the native allocator.
    // Only request native retirement of our own unbound, unselected records;
    // never free, unlink, retain an item pointer, or alter original messages.
    uintptr_t node{},previous=scene.head;if(!er::Read(scene.head,node))return false;
    unsigned visited{},retired{};
    while(node!=scene.head&&visited++<256){
        std::array<uintptr_t,3> links{};uint64_t key{};uint32_t flags{};
        if(!er::Read(node,links)||links[1]!=previous||!er::Read(links[2]+0x40,key))return false;
        const auto own=packIds.find(key);
        if(own!=packIds.end()&&!localIds.contains(key)&&retired<16){
            if(!Match(links[2],pack.messages[own->second])||!er::Read(links[2]+0x224,flags))return false;
            if(!(flags&0x1f)){
                const uint32_t request=flags|4;SIZE_T written{};
                if(!WriteProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(links[2]+0x224),&request,sizeof(request),&written)||written!=sizeof(request))return false;
                ++retired;
            }
        }
        previous=node;node=links[0];
    }
    uintptr_t tail{};return node==scene.head&&er::Read(scene.head+8,tail)&&tail==previous;
}
void* RegisterLocal(void* db,void* incoming,bool remote){
    const bool ours=localReceive&&localIndex<indices.size();
    uintptr_t existing=ours?cached[localIndex]:0;
    auto result=originalRegister(db,incoming,remote);
    if(!ours)return result;
    if(result){localResult=reinterpret_cast<uintptr_t>(result);return result;}
    Scene current{};
    // Native duplicate path destroys only the NEW input. The database owns the old node.
    if(!Current(db,current)||!(current==scene)||!InList(scene.db,existing)||!Match(existing,pack.messages[indices[localIndex]]))return nullptr;
    ++rebindings;localResult=existing;return reinterpret_cast<void*>(existing);
}
struct Sample{
    LARGE_INTEGER start{};
    Sample(){QueryPerformanceCounter(&start);}
    ~Sample(){LARGE_INTEGER end{};QueryPerformanceCounter(&end);static const auto frequency=[](){LARGE_INTEGER f{};QueryPerformanceFrequency(&f);return f.QuadPart;}();
        const auto us=static_cast<uint64_t>((end.QuadPart-start.QuadPart)*1000000/frequency);++ticks;microseconds+=us;
        auto previous=maximumMicros.load();while(us>previous&&!maximumMicros.compare_exchange_weak(previous,us)){}
    }
};
void Observe(void* instance,float delta){
    originalUpdate(instance,delta);
    if(disabled.load(std::memory_order_relaxed))return;
    Sample sample;
    try{
        if(updateThread&&updateThread!=GetCurrentThreadId()){Fail("Update thread changed");return;}updateThread=GetCurrentThreadId();
        Scene current{};
        if(paused.load(std::memory_order_relaxed)||!std::isfinite(delta)||delta<0||delta>=1||!Current(instance,current)){if(scene.db)Reset();return;}
        if(!(current==scene)){
            Reset();scene=current;++sceneGeneration;
            logFile.Write("Scene","generation="+std::to_string(sceneGeneration.load())+" map="+std::to_string(scene.map)+" selected="+std::to_string(indices.size()));
        }
        if(stable<120){++stable;return;}
        auto now=GetTickCount64();
        const bool selectionDue=now>=nextSelection;
        if(!SelectNearby(now))return;
        if(selectionDue&&!RetireUnselected()){Fail("Retirement list invariant failed");return;}
        if(indices.empty())return;
        if(now<registrationRetryAfter)return;
        if(complete){
            if(now<nextMaintenance)return;nextMaintenance=now+1000;
            WorkSample maintenance(1);
            unsigned count{};
            if(!Snapshot(count)){Fail("Maintenance list invariant failed");return;}
            if(std::all_of(present.begin(),present.end(),[](auto x){return x!=0;}))return;
            ++repairs;cursor=0;complete=false;repairOnly=true;attempts=0;
            logFile.Write("CacheRepair","Restore missing local entries only");
        }
        if(++spacing<4)return;spacing=0;
        WorkSample work(repairOnly?2u:0u);
        while(cursor<indices.size()&&repairOnly&&present[cursor])++cursor;
        if(cursor==indices.size()){
            complete=true;nextMaintenance=now+1000;
            logFile.Write("Registered","map="+std::to_string(scene.map)+" count="+std::to_string(indices.size())+" repair="+std::to_string(repairOnly)+"; visual verification still required");return;
        }
        unsigned before{};
        if(!Snapshot(before)){Fail("Registration list invariant failed");return;}
        // Avoid creating a second display instance for a node still bound by the game.
        if(bound[cursor]){++cursor;return;}
        uint32_t cacheLimit{};
        if(!er::Read(scene.db+0x20,cacheLimit)||cacheLimit<96||cacheLimit>192){Fail("Native cache capacity outside verified guard");return;}
        if(before>=cacheLimit-4&&!cached[cursor]){
            // Leave headroom. Spatial selection already reserves foreign and
            // protected own objects, including bindings in adjacent/old maps.
            // Never overflow capacity to repeatedly admit then expire a node.
            registrationRetryAfter=now+1000;
            if(!budgetWaiting){budgetWaiting=true;logFile.Write("CacheBudget","Waiting for native cache cleanup; retry at most once per second");}
            return;
        }
        if(budgetWaiting){budgetWaiting=false;registrationRetryAfter=0;logFile.Write("CacheBudget","Space available; registration resumed");}
        const auto& message=pack.messages[indices[cursor]];
        payload.fill(0);neutral(payload.data());message.WriteFields(payload);
        if(!validate(instance,payload.data())){Fail("Native payload validator rejected local record");return;}
        Scene finalCheck{};if(!Current(instance,finalCheck)||!(finalCheck==current)){Reset();return;}
        localIndex=cursor;localResult=0;localReceive=true;
        receive(instance,payload.data(),emptyGroups.data());
        localReceive=false;
        if(!localResult||!InList(scene.db,localResult)||!Match(localResult,message)){
            if(++attempts>=3){Fail("Native receive did not register a valid local node");return;}
            return;
        }
        cached[cursor]=localResult;present[cursor]=1;++registrations;++cursor;attempts=0;
    }catch(const std::exception& e){localReceive=false;Fail(e.what());}catch(...){localReceive=false;Fail("Unhandled replay exception");}
}
DWORD WINAPI Worker(void*)noexcept{
    try{
        auto mutexName=L"Local\\EROfflineMessages-"+std::to_wstring(GetCurrentProcessId());
        processInstance=CreateMutexW(nullptr,FALSE,mutexName.c_str());
        if(!processInstance||GetLastError()==ERROR_ALREADY_EXISTS){
            if(processInstance)CloseHandle(processInstance);processInstance=nullptr;return 1;
        }
        wchar_t file[32768]{};if(!GetModuleFileNameW(self,file,32768))return 1;
        auto directory=std::filesystem::path(file).parent_path();if(!logFile.Open(directory/L"EROfflineMessages.log"))return 1;
        logFile.Write("Loaded","0.1.5-dev1; resident-aware native cache budget; no capture or network code");
        if(!er::ExactExecutable()){Fail("Unsupported executable SHA-256");return 1;}
        if(er::HasAntiCheat()){Fail("Anti-cheat process present or inventory failed");return 1;}
        base=reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
        pack=er::MessagePack::Load(directory/L"EROfflineMessages.pack.json");
        spatial=std::make_unique<er::SpatialIndex>(pack);
        for(size_t i=0;i<pack.messages.size();++i)packIds.emplace(pack.messages[i].id,i);
        receive=reinterpret_cast<Receive>(base+0x1c2050);neutral=reinterpret_cast<Neutral>(base+0x1cfce0);validate=reinterpret_cast<Validate>(base+0x1c0c20);
        if(!Signature(0x1be980,{0x40,0x55,0x56,0x57,0x41,0x54,0x41,0x55,0x41,0x56,0x41,0x57,0x48,0x8b,0xec})
          ||!Signature(0x1bffc0,{0x40,0x55,0x56,0x57,0x48,0x83,0xec,0x70})
          ||!Signature(0x1c2050,{0x48,0x85,0xd2,0x0f,0x84,0x60,0x01,0x00,0x00})
          ||!Signature(0x1cfce0,{0x40,0x53,0x48,0x83,0xec,0x20,0xc7,0x41,0x44})
          ||!Signature(0x1c0c20,{0x48,0x89,0x5c,0x24,0x08,0x55,0x48,0x8b,0xec})
          ||!Signature(0x1c3c70,{0x8b,0x91,0x24,0x02,0x00,0x00,0x32,0xc0,0x0f,0x28,0xc1,0xf6,0xc2,0x19})){Fail("Native function signature mismatch");return 1;}
        logFile.Write("Waiting","Exact image and native signatures valid; waiting for offline gameplay before installing hooks");
        for(;;){if(er::HasAntiCheat()){Fail("Anti-cheat detected");return 1;}if(er::Offline(base))break;Sleep(1000);}
        if(MH_Initialize()!=MH_OK){Fail("MinHook initialization failed");return 1;}
        if(MH_CreateHook(reinterpret_cast<void*>(base+0x1bffc0),reinterpret_cast<void*>(&RegisterLocal),reinterpret_cast<void**>(&originalRegister))!=MH_OK
          ||MH_CreateHook(reinterpret_cast<void*>(base+0x1be980),reinterpret_cast<void*>(&Observe),reinterpret_cast<void**>(&originalUpdate))!=MH_OK){Fail("Native hook creation failed");return 1;}
        workerSafe=true;
        if(MH_EnableHook(MH_ALL_HOOKS)!=MH_OK){workerSafe=false;Fail("Native hook activation failed");return 1;}
        logFile.Write("Ready","Offline native replay hooks installed; source="+pack.source+" records="+std::to_string(pack.messages.size())+"; gestures=none; 1 Hz maintenance; no hot unload");
        unsigned counter{};
        for(;;){
            Sleep(1000);paused=std::filesystem::exists(directory/L"EROfflineMessages.pause");
            if(++counter%5==0&&er::HasAntiCheat()){workerSafe=false;Fail("Anti-cheat detected after initialization");}
            if(counter%10==0){
                auto calls=ticks.exchange(0),sum=microseconds.exchange(0),maximum=maximumMicros.exchange(0);
                logFile.Write("Performance","mod_avg_us="+std::to_string(calls?static_cast<double>(sum)/static_cast<double>(calls):0)+" mod_max_us="+std::to_string(maximum)+" updates="+std::to_string(calls)+" generations="+std::to_string(sceneGeneration.load())+" registrations="+std::to_string(registrations.load())+" rebindings="+std::to_string(rebindings.load())+" repairs="+std::to_string(repairs.load()));
                std::string timings="native_items="+std::to_string(nativeItems.load())+" local_cached="+std::to_string(cachedLocal.load())+" local_bound="+std::to_string(boundLocal.load());
                constexpr const char* labels[]={"registration","maintenance","cache_repair"};
                for(unsigned p=0;p<3;++p){auto n=workTimes[p].calls.exchange(0),total=workTimes[p].sum.exchange(0),peak=workTimes[p].maximum.exchange(0);
                    timings+=" "+std::string(labels[p])+"_calls="+std::to_string(n)+"_avg_us="+std::to_string(n?static_cast<double>(total)/static_cast<double>(n):0)+"_max_us="+std::to_string(peak);
                }
                logFile.Write("WorkPhases",timings);
            }
        }
    }catch(const std::exception& e){Fail(e.what());return 1;}catch(...){Fail("Worker initialization exception");return 1;}
}
}
BOOL WINAPI DllMain(HMODULE module,DWORD reason,void*){
    if(reason==DLL_PROCESS_ATTACH){self=module;DisableThreadLibraryCalls(module);HMODULE pinned{};
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(module),&pinned))return FALSE;
        auto thread=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(!thread)return FALSE;CloseHandle(thread);
    }return TRUE;
}
