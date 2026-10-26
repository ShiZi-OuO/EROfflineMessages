// Read-only, version-locked observer. No hooks, writes, calls into game code or networking.
#include <windows.h>
#include <tlhelp32.h>
#include <bcrypt.h>
#include <array>
#include <cstdint>
#include <filesystem>
#include <string>
#include <cstdio>
#include <cstring>
#include <limits>

namespace {
HMODULE self{};
HANDLE output=INVALID_HANDLE_VALUE;
constexpr uintptr_t NetSlot=0x3d61ee0;
constexpr uintptr_t NetVft=0x29cfeb8;
constexpr uintptr_t DbVft=0x29cec68;
constexpr uintptr_t ItemVft=0x29cee88;
constexpr char ExpectedSha[]="f9118fea2cfd8fa3901e8060bfadb1552cb2471771ded8a5b662c4e298ffb328";

void Log(const char* state,const std::string& detail) noexcept {
    SYSTEMTIME t{};GetLocalTime(&t);
    char prefix[128]{};
    std::snprintf(prefix,sizeof(prefix),"%04u-%02u-%02uT%02u:%02u:%02u.%03u [%s] ",t.wYear,t.wMonth,t.wDay,t.wHour,t.wMinute,t.wSecond,t.wMilliseconds,state);
    const auto line=std::string(prefix)+detail+"\r\n";
    DWORD written{};WriteFile(output,line.data(),static_cast<DWORD>(line.size()),&written,nullptr);
}
template<class T> bool Read(uintptr_t address,T& value) noexcept {
    if(address<0x10000 || address>std::numeric_limits<uintptr_t>::max()-sizeof(T))return false;
    SIZE_T copied{};
    return ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(address),&value,sizeof(T),&copied) && copied==sizeof(T);
}
bool HasAntiCheat() noexcept {
    auto snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);
    if(snapshot==INVALID_HANDLE_VALUE)return true;
    PROCESSENTRY32W p{};p.dwSize=sizeof(p);bool found=false;
    if(Process32FirstW(snapshot,&p))do {
        auto name=std::wstring(p.szExeFile);
        for(auto& c:name)c=static_cast<wchar_t>(towlower(c));
        if(name.find(L"easyanticheat")!=std::wstring::npos || name==L"start_protected_game.exe"){found=true;break;}
    }while(Process32NextW(snapshot,&p));
    CloseHandle(snapshot);return found;
}
bool ExactFile() {
    wchar_t path[32768]{};if(!GetModuleFileNameW(nullptr,path,32768))return false;
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    BCRYPT_ALG_HANDLE algorithm{};BCRYPT_HASH_HANDLE hash{};std::array<UCHAR,32> digest{};
    bool ok=BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)==0;
    if(ok)ok=BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0)==0;
    std::array<UCHAR,65536> buffer{};DWORD size{};
    while(ok){if(!ReadFile(file,buffer.data(),static_cast<DWORD>(buffer.size()),&size,nullptr)){ok=false;break;}if(!size)break;ok=BCryptHashData(hash,buffer.data(),size,0)==0;}
    if(ok)ok=BCryptFinishHash(hash,digest.data(),static_cast<ULONG>(digest.size()),0)==0;
    if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);CloseHandle(file);
    char hex[65]{};for(size_t i=0;i<digest.size();++i)std::snprintf(hex+i*2,3,"%02x",digest[i]);
    return ok && std::strcmp(hex,ExpectedSha)==0;
}
bool Snapshot(uintptr_t base,uintptr_t db,unsigned& count) {
    uintptr_t vft{},head{},node{},previous{};count=0;
    if(!Read(db,vft)||vft!=base+DbVft||!Read(db+0x10,head)||!head||!Read(head,node))return false;
    previous=head;
    while(node!=head && count<4096){
        std::array<uintptr_t,3> links{};uintptr_t type{};
        if(!Read(node,links)||links[1]!=previous||!Read(links[2],type)||type!=base+ItemVft)return false;
        // Anonymous layout only: block/position/phrase IDs; never read appearance or account fields.
        std::array<uint8_t,0x24> semantic{};
        if(!Read(links[2]+0x14,semantic))return false;
        previous=node;node=links[0];++count;
    }
    uintptr_t tail{};
    return node==head&&Read(head+8,tail)&&tail==previous;
}
DWORD WINAPI Worker(void*) noexcept {
    try{
        wchar_t path[32768]{};if(!GetModuleFileNameW(self,path,32768))return 1;
        auto logPath=std::filesystem::path(path).parent_path()/L"EROfflineObserver.log";
        output=CreateFileW(logPath.c_str(),FILE_APPEND_DATA,FILE_SHARE_READ,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(output==INVALID_HANDLE_VALUE)return 1;
        Log("Loaded","0.1.0 read-only observer; no hooks, writes, game calls or network requests");
        if(!ExactFile()){Log("Disabled","Executable SHA-256 mismatch");return 1;}
        if(HasAntiCheat()){Log("Disabled","Anti-cheat process present or process inventory unavailable");return 1;}
        auto base=reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
        Log("Ready","Exact 2.7.2.0 image; launch only after visual offline verification; polling 1 Hz");
        uintptr_t lastNet{},lastDb{};unsigned lastCount=~0u;
        for(unsigned tick=0;;++tick){
            if(tick%5==0 && HasAntiCheat()){Log("Disabled","Anti-cheat process appeared");return 1;}
            uintptr_t net{},vft{},db{},man1{},man2{},gm{},data{},settings{};unsigned count{};uint32_t map{},region{};
            uint8_t online=255,startOffline=255;
            if(Read(base+0x3d709a8,gm))Read(gm+0xbc8,online);
            if(Read(base+0x3d64fb8,data)&&Read(data+0x58,settings))Read(settings+0x18,startOffline);
            const bool valid=Read(base+NetSlot,net)&&Read(net,vft)&&vft==base+NetVft&&Read(net+0x78,db)&&Snapshot(base,db,count);
            if(valid){Read(net+0x1c,map);Read(net+0x24,region);Read(db+0x60,man1);Read(db+0x68,man2);}
            if(net!=lastNet||db!=lastDb||count!=lastCount||tick%10==0){
                char line[300]{};
                std::snprintf(line,sizeof(line),"valid=%u online=%u start_offline=%u net=%p db=%p entries=%u block_candidate=%08x region_candidate=%u managers=%p,%p",valid,online,startOffline,reinterpret_cast<void*>(net),reinterpret_cast<void*>(db),count,map,region,reinterpret_cast<void*>(man1),reinterpret_cast<void*>(man2));
                Log("Snapshot",line);lastNet=net;lastDb=db;lastCount=count;
            }
            Sleep(1000);
        }
    }catch(...){Log("Disabled","Observer exception");return 1;}
}
}
BOOL WINAPI DllMain(HMODULE module,DWORD reason,void*) {
    if(reason==DLL_PROCESS_ATTACH){self=module;DisableThreadLibraryCalls(module);
        HMODULE pinned{};
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(module),&pinned))return FALSE;
        auto worker=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(!worker)return FALSE;CloseHandle(worker);
    }
    return TRUE;
}
