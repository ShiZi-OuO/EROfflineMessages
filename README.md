# Elden Ring Offline Messages

Source corresponding to **Offline Messages 0.1.5**, published at [Nexus Mods](https://www.nexusmods.com/eldenring/mods/11469).

An offline-only native DLL for ME3 0.13.0. It replays a fixed snapshot of 23,439 authentic anonymous player-message samples through Elden Ring's native message markers, prompts and reading UI. Original positions, native phrase IDs and appraisal snapshots are preserved. This finite snapshot contains 476 original map IDs; it is not a complete server dump or a guarantee of every-map coverage. The replay DLL has no network collection code and does not directly edit save files.

## Build and review

See [build instructions](docs/BUILD.md) and [review notes](docs/NEXUS_REVIEW.md). Windows x64, Visual Studio 2022 C++ tools, Windows SDK and CMake 3.24+ are required. MinHook and nlohmann/json are vendored; no build-time dependency download is needed. Optional research tools are separate from the replay runtime and are not installation requirements.

```text
cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -DBUILD_TESTING=ON
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

The shipped DLL retains the internal build label **0.1.5-dev1**. The exact source/binary mapping is in [the frozen manifest](verification/cache-budget-dev5-build-manifest.json). A rebuild may have a different digest due to toolchain and linker differences; byte-identical rebuilding is not promised.

## Tested scope

Checked Windows x64 Steam App 1.17.2 / Regulation 1.17.3, EXE 2.7.2.0; exact image SHA-256 F9118FEA2CFD8FA3901E8060BFADB1552CB2471771DED8A5B662C4E298FFB328.

Current frozen DLL: Chinese/English same-record reading, three readable rounds each of title/death/travel/normal-restart recovery, natural cache-expiry recovery and original-position new-record readings. Five host tests and five independently rebuilt archive-source tests passed. [Validation records](verification/release015-validation.json) distinguish tests, actual captures and user confirmations. An extra start exited before gameplay for an unknown reason before a successful retry; this is documented. FPS/P99 comparisons and a one-hour soak were not performed. Other languages and other-mod combinations were not individually tested.

Native density and nearest-object rules remain active; not all samples appear simultaneously. Unsupported images or invalid offline conditions stop replay. Do not load multiple copies, replace active DLLs, edit saves or force-kill the game to clear caches.

## Installation, credits and licenses

[English](docs/INSTALL.world.en.md) · [中文](docs/INSTALL.world.zh-CN.md) · [Third-party components and research references](THIRD_PARTY.md)

This repository supplies source for review. Game assets, ME3 binaries, credentials, player identities, saves and private research inputs are not included. Constructed/stress fixtures and separate developer research tools are labelled and are not the default runtime data. Third-party components retain their respective licenses; no blanket MIT license is asserted over this entire mixed-source project.

## 中文说明

这是 Nexus 正式包 0.1.5 对应的源码。内部 DLL 标识为冻结实测的 0.1.5-dev1，原版句式本地化、原位置与采样时评价保持不变。仅脱机使用，默认 23,439 条真实匿名快照，476 个地图编号，覆盖仍有缺口。源码公开供构建与审核，不代表已经通过 Nexus 人工复核。构建步骤、许可证与验证范围见上方链接。
