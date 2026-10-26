#pragma once
#include <windows.h>
#include <array>
#include <cstdint>
#include <filesystem>
#include <limits>
#include <mutex>
#include <string>

namespace er {
inline constexpr uintptr_t NetSlot=0x3d61ee0,NetVft=0x29cfeb8,DbVft=0x29cec68,ItemVft=0x29cee88;
inline constexpr uintptr_t GameManSlot=0x3d709a8,MenuOnlineFlag=0x458fb9c,MenuOnlineEpoch=0x458fba0;
template<class T>bool Read(uintptr_t address,T& value)noexcept{
    if(address<0x10000||address>std::numeric_limits<uintptr_t>::max()-sizeof(T))return false;
    SIZE_T n{};return ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(address),&value,sizeof(T),&n)&&n==sizeof(T);
}
bool ExactExecutable();
bool HasAntiCheat()noexcept;
bool Offline(uintptr_t base)noexcept;
class LogFile{
    HANDLE file=INVALID_HANDLE_VALUE;std::mutex mutex;
public:
    bool Open(const std::filesystem::path&);
    void Write(const char*,const std::string&)noexcept;
};
}
