#include "RuntimeSupport.h"
#include <tlhelp32.h>
#include <bcrypt.h>
#include <cstdio>
#include <cwctype>
#include <cstring>

namespace er {
bool HasAntiCheat()noexcept{
    auto snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);if(snapshot==INVALID_HANDLE_VALUE)return true;
    PROCESSENTRY32W p{};p.dwSize=sizeof(p);bool found=false;
    if(!Process32FirstW(snapshot,&p)){CloseHandle(snapshot);return true;}
    do{std::wstring name(p.szExeFile);for(auto& c:name)c=static_cast<wchar_t>(std::towlower(c));
       if(name.find(L"easyanticheat")!=std::wstring::npos||name==L"start_protected_game.exe"){found=true;break;}
    }while(Process32NextW(snapshot,&p));CloseHandle(snapshot);return found;
}
bool ExactExecutable(){
    wchar_t path[32768]{};if(!GetModuleFileNameW(nullptr,path,32768))return false;
    auto file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);if(file==INVALID_HANDLE_VALUE)return false;
    BCRYPT_ALG_HANDLE alg{};BCRYPT_HASH_HANDLE hash{};std::array<UCHAR,32> digest{};
    bool ok=BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)==0;
    if(ok)ok=BCryptCreateHash(alg,&hash,nullptr,0,nullptr,0,0)==0;
    std::array<UCHAR,65536> data{};DWORD n{};
    while(ok){if(!ReadFile(file,data.data(),static_cast<DWORD>(data.size()),&n,nullptr)){ok=false;break;}if(!n)break;ok=BCryptHashData(hash,data.data(),n,0)==0;}
    if(ok)ok=BCryptFinishHash(hash,digest.data(),static_cast<ULONG>(digest.size()),0)==0;
    if(hash)BCryptDestroyHash(hash);if(alg)BCryptCloseAlgorithmProvider(alg,0);CloseHandle(file);
    char hex[65]{};for(size_t i=0;i<digest.size();++i)std::snprintf(hex+i*2,3,"%02x",digest[i]);
    return ok&&std::strcmp(hex,"f9118fea2cfd8fa3901e8060bfadb1552cb2471771ded8a5b662c4e298ffb328")==0;
}
bool Offline(uintptr_t base)noexcept{
    uintptr_t gm{};uint8_t online=255,menuOnline=255;int epoch{};
    return GetModuleHandleW(L"me3_mod_host.dll")&&Read(base+GameManSlot,gm)&&gm&&Read(gm+0xbc8,online)&&online==0
      &&Read(base+MenuOnlineEpoch,epoch)&&epoch<=-2&&Read(base+MenuOnlineFlag,menuOnline)&&menuOnline==0;
}
bool LogFile::Open(const std::filesystem::path& path){file=CreateFileW(path.c_str(),FILE_APPEND_DATA,FILE_SHARE_READ,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);return file!=INVALID_HANDLE_VALUE;}
void LogFile::Write(const char* state,const std::string& message)noexcept{
    try{std::lock_guard lock(mutex);SYSTEMTIME t{};GetLocalTime(&t);char stamp[100]{};
        std::snprintf(stamp,sizeof(stamp),"%04u-%02u-%02uT%02u:%02u:%02u.%03u [%s] ",t.wYear,t.wMonth,t.wDay,t.wHour,t.wMinute,t.wSecond,t.wMilliseconds,state);
        auto line=std::string(stamp)+message+"\r\n";DWORD n{};WriteFile(file,line.data(),static_cast<DWORD>(line.size()),&n,nullptr);
    }catch(...){}
}
}
