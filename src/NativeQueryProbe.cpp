// PRIVATE OFFLINE ABI EXPERIMENT. Never forwards a submission or authenticates.
// Synthetic token/client only; not the future online collector or release mod.
#include "RuntimeSupport.h"
#include <MinHook.h>
#include <atomic>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <vector>

namespace {
HMODULE self{};uintptr_t base{};er::LogFile log;
using Update=void(*)(void*,float);
using Query=int(*)(void*,void*,const void*);
Update originalUpdate{};
std::atomic<bool> done{};
unsigned stable{};
struct Area {uint32_t first,second;};
struct Vector {uintptr_t begin,end,capacity;};
struct Request {Vector areas,groups;};
static_assert(sizeof(Area)==8&&sizeof(Vector)==24&&sizeof(Request)==48);
thread_local bool ours{};
thread_local void* expectedToken{};
thread_local const Request* expectedInput{};
thread_local bool captured{},copied{};
thread_local unsigned hits{};
bool Signature(uintptr_t rva,std::initializer_list<uint8_t> expected){
    std::array<uint8_t,32> actual{};SIZE_T got{};
    return ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(base+rva),actual.data(),expected.size(),&got)
        &&got==expected.size()&&std::equal(expected.begin(),expected.end(),actual.begin());
}
void BlockSubmission(void* client,void* token,const void* parameters){
    // NEVER call the original. Not even an unrelated operation is forwarded.
    if(!ours)return;
    ++hits;
    uint32_t variant{};Request copy{};
    if(!er::Offline(base)||client!=reinterpret_cast<void*>(0x12340000)||token!=expectedToken
       ||!er::Read(reinterpret_cast<uintptr_t>(parameters)+0x3d0,variant)||variant!=18
       ||!er::Read(reinterpret_cast<uintptr_t>(parameters),copy)||!expectedInput)return;
    const auto& input=expectedInput->areas;
    if(copy.areas.end<copy.areas.begin||copy.areas.end-copy.areas.begin!=input.end-input.begin
       ||copy.areas.capacity<copy.areas.end||copy.groups.begin!=copy.groups.end)return;
    const size_t size=static_cast<size_t>(input.end-input.begin);
    if(size>8*sizeof(Area)||size%sizeof(Area))return;
    std::array<Area,8> values{};SIZE_T got{};
    if(!ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(copy.areas.begin),values.data(),size,&got)||got!=size)return;
    captured=std::memcmp(values.data(),reinterpret_cast<void*>(input.begin),size)==0;
    copied=copy.areas.begin!=input.begin;
}
void Observe(void* db,float delta){
    originalUpdate(db,delta);
    if(done||!std::isfinite(delta)||delta<=0||delta>=1||!er::Offline(base))return;
    uintptr_t net{},actualDb{},type{};uint32_t map{};
    if(!er::Read(base+er::NetSlot,net)||!er::Read(net,type)||type!=base+er::NetVft
       ||!er::Read(net+0x78,actualDb)||actualDb!=reinterpret_cast<uintptr_t>(db)
       ||!er::Read(net+0x1c,map)||map==UINT32_MAX)return;
    if(stable++<120)return;
    if(done.exchange(true))return;
    try{
        // Source fields are candidate query pairs, not verified server targets.
        const std::array<Area,2> areas{{{31030,3103001},{30020,3002001}}};
        std::array<uint64_t,3> token{0x11223344,0x55667788,0};
        std::array<uintptr_t,2> fakeInterface{0,0x12340000};
        const auto query=reinterpret_cast<Query>(base+0x1df7760);
        for(unsigned count=1;count<=2;++count){
            const auto first=reinterpret_cast<uintptr_t>(areas.data());
            Request input{{first,first+count*sizeof(Area),first+sizeof(areas)},{0,0,0}};
            const auto before=input;const auto originalToken=token;
            ours=true;expectedInput=&input;expectedToken=token.data();captured=false;copied=false;hits=0;
            const auto result=query(fakeInterface.data(),token.data(),&input);
            ours=false;expectedInput=nullptr;expectedToken=nullptr;
            const bool unchanged=std::memcmp(&before,&input,sizeof(input))==0&&token==originalToken;
            const bool pass=result==0&&hits==1&&captured&&copied&&unchanged;
            log.Write(pass?"ABI_PASS":"ABI_FAIL","areas="+std::to_string(count)+" variant=18 hits="+std::to_string(hits)
                +" deep_copy="+std::to_string(copied)+" unchanged_input_and_fake_token="+std::to_string(unchanged)
                +"; synthetic client/token only; submission blocked; actual_network_requests=0");
            if(!pass)return;
        }
        log.Write("Complete","Two synthetic offline calls passed; no proof of authentication, remote area mapping or server receipt");
    }catch(...){ours=false;log.Write("ABI_FAIL","Probe exception; no submission forwarded");}
}
DWORD WINAPI Worker(void*){
    try{
        wchar_t file[32768]{};if(!GetModuleFileNameW(self,file,32768))return 1;
        if(!log.Open(std::filesystem::path(file).parent_path()/L"EROfflineQueryProbe.log"))return 1;
        log.Write("Loaded","PRIVATE OFFLINE ONLY; all bloodmessage submissions blocked; no capture or authentication");
        if(!er::ExactExecutable()||er::HasAntiCheat()||GetModuleHandleW(L"EROfflineMessages.dll")){
            log.Write("Refused","Exact image, no anti-cheat and no replay DLL required");return 1;
        }
        base=reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
        if(!Signature(0x1df7020,{0xe9,0x10,0x86,0x94,0x03})
          ||!Signature(0x1df7760,{0x48,0x83,0xec,0x28,0x48,0x8b,0x49,0x08,0xe8,0x53,0xfb,0xff,0xff})
          ||!Signature(0x1df72c0,{0x4c,0x8b,0xdc,0x57,0x48,0x81,0xec,0x10,0x04,0x00,0x00})
          ||!Signature(0x1be980,{0x40,0x55,0x56,0x57,0x41,0x54,0x41,0x55,0x41,0x56,0x41,0x57,0x48,0x8b,0xec})){
            log.Write("Refused","Native signature mismatch; no hooks installed");return 1;
        }
        for(unsigned n=0;n<300&&!er::Offline(base);++n){if(er::HasAntiCheat())return 1;Sleep(1000);}
        if(!er::Offline(base)||er::HasAntiCheat())return 1;
        if(MH_Initialize()!=MH_OK)return 1;
        void* unused{};
        if(MH_CreateHook(reinterpret_cast<void*>(base+0x1df7020),reinterpret_cast<void*>(&BlockSubmission),&unused)!=MH_OK
          ||MH_CreateHook(reinterpret_cast<void*>(base+0x1be980),reinterpret_cast<void*>(&Observe),reinterpret_cast<void**>(&originalUpdate))!=MH_OK)return 1;
        if(MH_EnableHook(MH_ALL_HOOKS)!=MH_OK)return 1;
        log.Write("Ready","Offline update-thread experiment armed; submission hook never forwards; normal exit required");
    }catch(...){return 1;}
    return 0;
}
}
BOOL WINAPI DllMain(HMODULE module,DWORD reason,void*){
    if(reason==DLL_PROCESS_ATTACH){self=module;DisableThreadLibraryCalls(module);HMODULE pinned{};
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(module),&pinned))return FALSE;
        const auto thread=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(!thread)return FALSE;CloseHandle(thread);
    }return TRUE;
}
