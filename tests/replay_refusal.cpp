// Exercise the exact shipped DLL in a disposable host, never in the game.
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>

int wmain(int argc,wchar_t** argv){
    if(argc!=3)return 2;
    namespace fs=std::filesystem;
    auto run=fs::path(argv[2])/(std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetTickCount64()));
    fs::create_directories(run/L"first");fs::create_directories(run/L"second");
    auto first=run/L"first/EROfflineMessages.dll",second=run/L"second/EROfflineMessages-copy.dll";
    fs::copy_file(argv[1],first);fs::copy_file(argv[1],second);
    if(!LoadLibraryW(first.c_str()))return 3;
    auto mutexName=L"Local\\EROfflineMessages-"+std::to_wstring(GetCurrentProcessId());
    HANDLE mutex{};
    for(unsigned n=0;n<100&&!mutex;++n){mutex=OpenMutexW(SYNCHRONIZE,FALSE,mutexName.c_str());if(!mutex)Sleep(20);}
    if(!mutex){std::cerr<<"First DLL instance did not create its process guard\n";return 1;}
    CloseHandle(mutex);
    if(!LoadLibraryW(second.c_str()))return 3;
    std::string text;
    for(unsigned n=0;n<100;++n){
        std::ifstream log(run/L"first/EROfflineMessages.log");std::ostringstream contents;contents<<log.rdbuf();text=contents.str();
        if(text.find("Unsupported executable SHA-256")!=std::string::npos)break;
        Sleep(20);
    }
    Sleep(200);
    if(text.find("Unsupported executable SHA-256")==std::string::npos
      ||text.find("Ready")!=std::string::npos||fs::exists(run/L"second/EROfflineMessages.log")){
        std::cerr<<"Expected unsupported-image refusal and duplicate-instance guard\n";return 1;
    }
    std::cout<<"PASS: real DLL refused this unsupported host before hooks; copied second instance stopped before initialization\n";
    // DLLs pin themselves. Keep these test-only artifacts for inspection until
    // this helper exits; no loaded file is replaced or force-unloaded.
    return 0;
}
