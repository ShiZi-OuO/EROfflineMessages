# Nexus manual-review build reference

Mod: https://www.nexusmods.com/eldenring/mods/11469  
Main file ID: 52756  
Distribution: 0.1.5, internal DLL label 0.1.5-dev1.

Uploaded archive SHA-256:
`8a69a67059cae9bb8ab0f3d3a6cb6de103d7201a7cc10b9b24864655f286778f`

Shipped `natives/EROfflineMessages.dll` SHA-256:
`b9e623b68ac2415df24bbcd5f7f67415c9cdbc1f5ff4e63ffc08feacf47b82e5`

The frozen manifest in `verification/cache-budget-dev5-build-manifest.json` covers 14 runtime source/build inputs; these inputs were checked unchanged before upload. This review repository is based on the source directory of that exact uploaded archive. README/review notes and verification metadata were added for reviewers, without changing runtime inputs. Source history and research tools retained from the original archive are not claims that old builds passed current acceptance.

Build on Windows x64 with VS2022 C++ tools, Windows SDK and CMake 3.24+:

```text
cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -DBUILD_TESTING=ON
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

Replay output: `build/bin/Release/EROfflineMessages.dll`. Observer, query-probe and capture DLL targets are separate development tools; only the replay DLL is installed. `src/NativeReplay.cpp`, `src/RuntimeSupport.cpp`, `src/MessagePack.cpp`, `src/SpatialIndex.cpp` and `src/CacheBudget.h` implement the replay, validation and bounded selection. MinHook provides native hooks. Vendored dependencies and licenses are identified in THIRD_PARTY.md.

The replay has no networking/collection code and does not directly edit saves. Its native hooks and memory access are intentional game-mod functionality. It checks the supported game image, native signatures and offline state. No claim is made that these facts guarantee scanner acceptance. Build requirements and limitations are further documented in docs/BUILD.md.

The original archive also contains anonymous snapshot data, guides, licenses, screenshots, source and validation records. This repository deliberately includes no compiled DLL, game assets, account data, authentication tickets or private research inputs. Rebuild steps are reproducible, but byte-identical DLL output across differing compiler/linker environments is not promised.
