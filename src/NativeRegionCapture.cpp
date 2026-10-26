// PRIVATE LIMITED EXPERIMENT, not the offline replay mod. Disabled by default.
// Normal native session only; no authentication calls, ticket access or sockets.
#include "RuntimeSupport.h"
#include <MinHook.h>
#include <json.hpp>
#include <intrin.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <fstream>
#include <mutex>
#include <vector>

namespace {
using Json=nlohmann::json;
struct Area {uint32_t first,second;bool operator==(const Area&)const=default;};
struct Vector {uintptr_t begin,end,capacity;};
struct Request {Vector areas,groups;};
static_assert(sizeof(Area)==8&&sizeof(Vector)==24&&sizeof(Request)==48);
using Query=int(*)(void*,void*,const Request*);
using Receive=void(*)(void*,const void*,const void*);
Query originalQuery{};Receive originalReceive{};
HMODULE self{};uintptr_t base{};er::LogFile log;
HANDLE processInstance{};
std::filesystem::path directory;
std::mutex mutex;Json records=Json::array(),events=Json::array();
std::atomic<unsigned> redirected{},observed{},received{},failures{};
std::atomic<bool> replacementCalled{};
std::atomic<bool> baseline{},completed{},expired{},stop{};
std::atomic_flag queryBusy=ATOMIC_FLAG_INIT;
ULONGLONG lastQuery{},started{};
constexpr Area destination{3002001,3002001}; // Stormfoot: new official-sample area
thread_local bool forwarded{};
int Forward(void* client,void* token,const Request* input){forwarded=true;return originalQuery(client,token,input);}
bool Signature(uintptr_t rva,std::initializer_list<uint8_t> expected){
    std::array<uint8_t,32> actual{};SIZE_T got{};
    return ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(base+rva),actual.data(),expected.size(),&got)
        &&got==expected.size()&&std::equal(expected.begin(),expected.end(),actual.begin());
}
bool Online(uint32_t& map,uint32_t& region){
    uintptr_t game{},net{},type{};uint8_t connected{};
    return er::Read(base+er::GameManSlot,game)&&er::Read(game+0xbc8,connected)&&connected==1
        &&er::Read(base+er::NetSlot,net)&&er::Read(net,type)&&type==base+er::NetVft
        &&er::Read(net+0x1c,map)&&map!=UINT32_MAX&&er::Read(net+0x24,region);
}
bool Areas(const Vector& input,std::vector<Area>& output){
    if(input.end<input.begin||input.capacity<input.end)return false;
    const auto size=input.end-input.begin;
    if(!size||size%sizeof(Area)||size>8*sizeof(Area))return false;
    output.resize(size/sizeof(Area));SIZE_T got{};
    return ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(input.begin),output.data(),size,&got)&&got==size;
}
int QueryCore(void* client,void* token,const Request* input){
    // Never manufacture a token, schedule a query or call authentication.
    if(queryBusy.test_and_set())return Forward(client,token,input);
    struct Unlock {~Unlock(){queryBusy.clear();}} unlock;
    uint32_t map{},region{};Request request{};std::vector<Area> source;
    if(stop||completed||expired||!token||!Online(map,region)||map!=0x0b050000
        ||!er::Read(reinterpret_cast<uintptr_t>(input),request)||!Areas(request.areas,source))
        return Forward(client,token,input);
    const auto now=GetTickCount64();
    if(!baseline){
        // First natural request is observed and forwarded unchanged. Verify the
        // interior pattern before attempting the one allowed replacement.
        const bool current=std::find(source.begin(),source.end(),Area{region,region})!=source.end();
        const bool interior=std::all_of(source.begin(),source.end(),[](const auto& a){return a.first==a.second;});
        Json pairs=Json::array();for(auto a:source)pairs.push_back({a.first,a.second});
        {std::lock_guard lock(mutex);events.push_back({{"kind","baseline_natural_query"},{"pairs",pairs},
            {"map",map},{"region",region},{"pattern_matches",current&&interior}});}
        ++observed;baseline=current&&interior;lastQuery=now;
        if(!baseline)stop=true;
        return Forward(client,token,input);
    }
    if(now-lastQuery<10000)return Forward(client,token,input);
    unsigned expected=0;if(!redirected.compare_exchange_strong(expected,1))return Forward(client,token,input);
    const auto ledger=directory/L"ERNativeRegionCapture.budget.json";
    const auto reservation=CreateFileW(ledger.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(reservation==INVALID_HANDLE_VALUE){stop=true;return Forward(client,token,input);}
    constexpr char ledgerText[]="{\"replacements_reserved\":1,\"automatic_retry\":false}\n";
    DWORD written{};const bool reserved=WriteFile(reservation,ledgerText,sizeof(ledgerText)-1,&written,nullptr)
        &&written==sizeof(ledgerText)-1&&FlushFileBuffers(reservation);
    CloseHandle(reservation);
    if(!reserved){stop=true;return Forward(client,token,input);}
    ++observed;
    Request replacement=request;
    replacement.areas={reinterpret_cast<uintptr_t>(&destination),reinterpret_cast<uintptr_t>(&destination)+sizeof(Area),reinterpret_cast<uintptr_t>(&destination)+sizeof(Area)};
    // Keep original group vector and token; the exact native wrapper deep-copies
    // both vectors before returning, as checked by the separate offline probe.
    replacementCalled=true;const auto result=Forward(client,token,&replacement);
    {std::lock_guard lock(mutex);events.push_back({{"kind","one_natural_query_replaced"},
        {"target_pair",{destination.first,destination.second}},{"result",result}});}
    return result;
}
int QueryHook(void* client,void* token,const Request* input){
    forwarded=false;
    try{return QueryCore(client,token,input);}
    catch(...){stop=true;++failures;return forwarded?1:Forward(client,token,input);}
}
void ReceiveHook(void* db,const void* payload,const void* groups){
    // Only the normal BloodMessageDownloadJob receipt call site is sampled.
    // No appearance/name/original-key ranges are read or retained.
    try{if(!stop&&!expired&&reinterpret_cast<uintptr_t>(_ReturnAddress())==base+0xa01e55&&received<2048){
        uint32_t map{},region{},area{};std::array<uint32_t,2> location{};
        std::array<float,4> position{};std::array<uint16_t,8> phrase{};
        const auto p=reinterpret_cast<uintptr_t>(payload);
        if(Online(map,region)&&er::Read(p+0x1c0,location)&&er::Read(p+0x1c8,position)
           &&er::Read(p+0x1d8,phrase)&&er::Read(p+0x1f8,area)
           &&std::all_of(position.begin(),position.end(),[](float v){return std::isfinite(v)&&std::abs(v)<=1000000;})){
            const bool target=redirected&&location[0]==0x1e020000&&area==3002001;
            if(target||!redirected){
                Json record={{"map",location[0]},{"area",area},{"secondary_area",location[1]},
                    {"position",{position[0],position[1],position[2]}},{"yaw",position[3]},
                    {"template1",phrase[0]},{"word1",phrase[2]},{"conjunction",phrase[3]},
                    {"template2",phrase[4]},{"word2",phrase[5]},{"good",phrase[6]},{"poor",phrase[7]}};
                {std::lock_guard lock(mutex);if(records.size()<2048){records.push_back(std::move(record));++received;}}
                if(target)completed=true;
            }
        }else ++failures;
    }}catch(...){stop=true;++failures;}
    originalReceive(db,payload,groups);
}
void Save(){
    Json result;
    {std::lock_guard lock(mutex);result={{"type","unverified_native_region_capture"},{"official_samples",0},
        {"records",records},{"events",events},{"baseline_verified",baseline.load()},
        {"natural_queries_observed",observed.load()},{"replacement_attempt_claimed",redirected.load()},
        {"native_replacement_call_attempted",replacementCalled.load()},
        {"target_receipt_observed",completed.load()},{"expired",expired.load()},
        {"stopped",stop.load()},{"invalid_semantic_reads",failures.load()},
        {"extra_queries_created",0},{"identity_exported",false}};}
    const auto temporary=directory/L"ERNativeRegionCapture.pending.json";
    const auto output=directory/L"ERNativeRegionCapture.candidates.json";
    {std::ofstream file(temporary,std::ios::binary);file<<result.dump(2)<<'\n';if(!file)throw std::runtime_error("Candidate output failed");}
    if(!MoveFileExW(temporary.c_str(),output.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
        throw std::runtime_error("Candidate checkpoint failed");
}
DWORD WINAPI Worker(void*){
    try{
        wchar_t file[32768]{};if(!GetModuleFileNameW(self,file,32768))return 1;
        directory=std::filesystem::path(file).parent_path();
        if(!log.Open(directory/L"ERNativeRegionCapture.log"))return 1;
        const auto mutexName=L"Local\\ERNativeRegionCapture-"+std::to_wstring(GetCurrentProcessId());
        processInstance=CreateMutexW(nullptr,FALSE,mutexName.c_str());
        if(!processInstance||GetLastError()==ERROR_ALREADY_EXISTS){log.Write("Refused","Duplicate collector");return 1;}
        std::ifstream planFile(directory/L"ERNativeRegionCapture.plan.json");
        const auto plan=Json::parse(planFile,nullptr,false);
        if(plan.is_discarded()||plan.value("enabled",false)!=true
           ||plan.value("authorization",std::string{})!="EXPLICIT_USER_NATIVE_ONLINE_PILOT"
           ||plan.value("maximum_replacements",0)!=1||plan.value("minimum_interval_seconds",0)!=10){
            log.Write("Refused","Disabled by default; distinct explicit online native pilot authorization required");return 1;
        }
        if(!er::ExactExecutable()||er::HasAntiCheat()||GetModuleHandleW(L"EROfflineMessages.dll")||GetModuleHandleW(L"EROfflineQueryProbe.dll")){
            log.Write("Refused","Exact image, no EAC process and no other experiment/replay DLL required; no bypass attempted");return 1;
        }
        base=reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
        if(!Signature(0x1df7760,{0x48,0x83,0xec,0x28,0x48,0x8b,0x49,0x08,0xe8,0x53,0xfb,0xff,0xff})
           ||!Signature(0x1bd610,{0xe9,0x3b,0x4a,0x00,0x00})){log.Write("Refused","Signature mismatch");return 1;}
        if(std::filesystem::exists(directory/L"ERNativeRegionCapture.candidates.json")
           ||std::filesystem::exists(directory/L"ERNativeRegionCapture.budget.json")){
            log.Write("Refused","Archive prior private candidates first; no overwrite on a new run");return 1;
        }
        if(MH_Initialize()!=MH_OK)return 1;
        if(MH_CreateHook(reinterpret_cast<void*>(base+0x1df7760),reinterpret_cast<void*>(&QueryHook),reinterpret_cast<void**>(&originalQuery))!=MH_OK
           ||MH_CreateHook(reinterpret_cast<void*>(base+0x1bd610),reinterpret_cast<void*>(&ReceiveHook),reinterpret_cast<void**>(&originalReceive))!=MH_OK)return 1;
        if(MH_EnableHook(MH_ALL_HOOKS)!=MH_OK)return 1;
        started=GetTickCount64();log.Write("Ready","PRIVATE LIMITED native online pilot; one natural query replacement; no authentication or extra requests; normal exit required");
        for(;;){Sleep(1000);if(GetTickCount64()-started>600000)expired=true;
            if(er::HasAntiCheat())stop=true;Save();
        }
    }catch(...){stop=true;log.Write("Stopped","Experiment exception; further queries forwarded unchanged");return 1;}
}
}
BOOL WINAPI DllMain(HMODULE module,DWORD reason,void*){
    if(reason==DLL_PROCESS_ATTACH){self=module;DisableThreadLibraryCalls(module);HMODULE pinned{};
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(module),&pinned))return FALSE;
        const auto thread=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(!thread)return FALSE;CloseHandle(thread);
    }return TRUE;
}
