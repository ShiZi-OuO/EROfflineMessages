# Reproducing the development build

The installable client-received snapshot has version-specific gameplay evidence. See `verification/validation.json` in the package for measured scope and incomplete checks. Building does not confer gameplay acceptance.

Requirements: Windows x64, CMake 3.24+, Visual Studio 2022 C++ build tools and Windows SDK. The DLL uses C++20 and the static MSVC runtime. Dependencies are vendored: MinHook and nlohmann/json; no build-time download is required.

From an x64 Native Tools command prompt, in the project directory:

```text
cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -DBUILD_TESTING=ON
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

Do not rebuild the replay DLL while the game is using it. The current supported image is strictly SHA-256 locked; see the root README for its version. Passing build tests proves parsing and payload construction, not visibility or game stability.

Development profiles use `../build/bin/Release` DLL paths. Copy the chosen constructed fixture to `build/bin/Release/EROfflineMessages.pack.json` before launching the replay profile. Its positions are block-local, not Havok coordinates. The data file is read once at startup.

Use `tools/launch-dev.ps1` to select `baseline`, `observer` or `replay-prototype`. It explicitly uses the supplied game's `bin/me3.exe`; it does not rely on the Windows file association. Keep Steam running. These profiles set `start_online=false`, load no asset packages and use the normal save selection. Normal gameplay can autosave.

The Python research helpers additionally require Python 3.12, pefile and capstone. They are not end-user dependencies. `observe.py` and `inspect_display.py` open the verified offline game with query/read rights only. They export allowlisted anonymous fields and do not write game memory or saves.

Optional research dependency versions used on this host are pinned in `tools/requirements-research.txt`; `cryptography` is only needed by the separate read-only archive/map research script. That script is GPL-3.0-only and requires a separately supplied public key source and the user's own local game decompressor; neither is bundled in the Mod. See `docs/research/map-data.md` and `THIRD_PARTY.md`. Do not include raw extracted game assets in an installation archive.

# 中文构建说明

当前交付为可安装真实客户端有限快照，实测范围及未验证项见包内 verification/validation.json。构建命令同上，需要 Windows x64、CMake 3.24 及以上、VS 2022 C++ 工具与 Windows SDK。依赖已随源码保存，无需在构建时联网下载。

修改 DLL 前先从游戏菜单正常退出。构建及单元测试通过只代表代码和数据校验通过，不代表看见标记、能够阅读或生命周期测试通过。

开发配置分为无 Mod 基线、只读观察和原生回放；启动工具显式指定游戏目录内的 ME3，避免旧版 `.me3` 关联。数据包相对 DLL 定位，启动时读取一次。当前构造数据使用区块内坐标。研究用 Python 工具不是用户安装依赖。

## Validate the default snapshot / 校验默认快照

```text
build\Release\er_pack_check.exe data\official-expansion-23439-v10.json
```

Expected: `source=official_sample records=23439 maps=476 maximum_per_map=468 nearby_selection_limit=96`. The production parser is shared with the DLL. The replay DLL is `build/bin/Release/EROfflineMessages.dll`; the observer DLL is a separate research target and must not be added to the installation profile. The separately labelled constructed fixtures are optional research data, not the default pack. The default data file must be copied next to the replay DLL as `EROfflineMessages.pack.json`.

The delivered runtime uses the static MSVC runtime and imports only Windows `KERNEL32.dll` and `bcrypt.dll`. Its SHA-256 is recorded separately from the ZIP. A rebuilt DLL can have a different digest due to compiler/linker paths, timestamps or toolchain; byte-identical output is not claimed. Source extracted from the 23,385-record RC1 archive was independently rebuilt successfully and passed all four core tests plus the full 23,385-record production-parser check; see `verification/source-archive-rebuild-23385.json`. That rebuilt DLL was not used in the game; that historical 0.1.4 distribution retained its original game-tested DLL. The current 0.1.5 frozen source was independently rebuilt from the 23,439-record preview-r2 archive and passed all five default tests; see the final validation record. The original game-tested DLL remains shipped, not the rebuilt output.

预期校验输出如上。观察 DLL 仅供研究，不要合并进安装配置。新编译 DLL 的摘要可能因工具链、路径、链接时间等变化；本工程提供可复现构建步骤，不承诺二进制逐字节相同。不要用新编译结果的摘要代替实际实机测试 DLL 的摘要。


The current runtime source is 0.1.5-dev1. The default CTest run has five tests, including native_cache_budget_guards. It uses a per-map spatial index, at most 96 candidates and a resident-aware nearest prefix. Foreign nodes and protected own nodes outside that prefix reserve capacity. Eight slots are reserved when planning selection; new admission waits at capacity minus four. Original objects and display bindings are never forcibly freed or unlinked by the Mod. Only the existing native retirement request for own unbound unselected records is used. The failed dev4 map-variant experiment remains excluded.

当前源码为 0.1.5-dev1，默认 CTest 为 5 项。修正版在选择附近记录前计算驻留预算，预留原版对象与未纳入选择但仍受保护的 Mod 对象空间；候选最多 96 条，实际数量随预算减少。该限制不减少数据文件中的地图或记录总数。源码归档与本版 DLL 的对应关系见 build-source-manifest.json。0.1.4 的归档重建记录仅为历史，不是本版重建证据。可选协议测试依赖私人研究夹具，不包含在上述五项默认测试中。

For a chosen expanded pack, pass that JSON to `er_pack_check.exe`, then copy it next to the DLL as `EROfflineMessages.pack.json`. The parser accepts more than 96 records per map; 96 is the nearby selection bound, not a per-map data limit. Preserve the original map IDs and block-local coordinates. Constructed fixtures and quarantined candidates must not be merged into official snapshots.

扩充包用相同生产解析器校验，再将选定 JSON 复制到 DLL 旁并命名为 `EROfflineMessages.pack.json`。单地图总条数可以超过 96，96 只是附近选择上限。保留原地图编号和区块内坐标，不要把构造测试或隔离候选合并进官方样本。安装包包含源码与第三方许可；可选协议研究工具不属于回放 DLL 的运行依赖，不能靠重新运行采集工具复现已冻结快照。

The stable 0.1.5 distribution retains the exact game-tested 0.1.5-dev1 DLL. Its source manifest has 14 runtime inputs. Packaging and documentation changes do not rebuild that binary.
