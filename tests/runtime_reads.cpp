#include "RuntimeSupport.h"
#include <iostream>

int main(){
    auto check=[](bool condition,const char* label){if(!condition){std::cerr<<label<<'\n';return false;}return true;};
    uint64_t value{};
    if(!check(!er::Read(0,value),"null read refused")
      ||!check(!er::Read(0x1000,value),"low address refused")
      ||!check(!er::Read(UINTPTR_MAX-3,value),"wrapped range refused"))return 1;
    SYSTEM_INFO system{};GetSystemInfo(&system);
    auto memory=static_cast<uint8_t*>(VirtualAlloc(nullptr,system.dwPageSize*2,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    if(!memory)return 2;
    auto address=reinterpret_cast<uintptr_t>(memory);
    const uint64_t expected=0x123456789abcdef0;
    std::memcpy(memory,&expected,sizeof(expected));
    bool ok=check(er::Read(address,value)&&value==expected,"valid readable object");
    DWORD previous{};
    if(!VirtualProtect(memory+system.dwPageSize,system.dwPageSize,PAGE_NOACCESS,&previous)){VirtualFree(memory,0,MEM_RELEASE);return 2;}
    ok=check(!er::Read(address+system.dwPageSize,value),"inaccessible page refused")&&ok;
    ok=check(!er::Read(address+system.dwPageSize-4,value),"cross-page partial read refused")&&ok;
    VirtualFree(memory,0,MEM_RELEASE);
    ok=check(!er::Read(address,value),"released allocation refused")&&ok;
    return ok?0:1;
}
