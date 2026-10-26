# Third-party components and research references

Bundled build dependencies:

| Component | Location | License |
| --- | --- | --- |
| MinHook 1.3.3 | `third_party/minhook` | Full upstream license in `third_party/minhook/LICENSE.txt`, including the decoder notices. Copied read-only from the existing DS3 project's vendored dependency. |
| nlohmann/json 3.12.0 | `third_party/json/json.hpp` | MIT; full text in `third_party/json/LICENSE.MIT`. Copied read-only from the existing DS3 project's vendored dependency. |

Runtime dependency: [ME3 0.13.0](https://github.com/garyttierney/me3/releases/tag/v0.13.0), installed separately. This project does not redistribute the game, its resources, or the ME3 binaries.

Research references, not bundled source code:

- [DS3OfflineMessages](https://github.com/ShiZi-OuO/DS3OfflineMessages): native replay ownership, maintenance and measurement lessons. Its game addresses and layouts are not used as Elden Ring offsets.
- [fromsoftware-rs, fixed research revision](https://github.com/vswarte/fromsoftware-rs/tree/6da5f80ae561944f45470e353be996a05137095a): structure naming and field leads, checked against this machine's exact game image. The repository has custom non-AI-training licenses; do not label it ordinary MIT/Apache or copy its source without preserving its actual terms.
- [waygate-server bloodmessage research](https://github.com/vswarte/waygate-server/blob/197ef607eccb912299d773df7c23ae0268164ab2/message/src/eldenring/bloodmessage.rs): protocol field leads only. The project's independently implemented private experiments are separate from the replay DLL; the AGPL reference implementation is not bundled or linked.

All game software, names and assets belong to their respective rights holders. No game assets are bundled in this project.

## Optional research tools

`tools/static-code-analysis` uses dearxan **0.5.2** (MIT OR Apache-2.0, MIT option selected) and pelite **0.10.0** (MIT). Direct licences are under that tool's `licenses/`; Cargo.lock fixes its dependency graph. Only dearxan's static analysis is enabled, not its runtime disabler. It reads an EXE into its own byte buffer, does not load the game, open a process, patch protections or connect to a server. Local decoded game-code windows stay private and must not be distributed. This developer tool is not linked into or required by the offline replay DLL.

`tools/research_map_graces.py` is a separate GPL-3.0-only file-format research tool. It is not linked into either native DLL and is not required to install or play this Mod. Its narrow readers were developed against the archive/MSBE format implementations in [SoulsFormatsNEXT revision 4b881c3](https://github.com/soulsmods/SoulsFormatsNEXT/tree/4b881c3aa520771603afb8808d40d296c78846f1); the GPL text is included in `licenses/research-tools-GPL-3.0.txt`.

Archive format and public key references were checked in [UXM Selective Unpack revision 9501be8](https://github.com/Nordgaren/UXM-Selective-Unpack/tree/9501be87e272b6dae55e60a13c3f4753ca6fb3bb). UXM binaries and key source files are not redistributed. The research script accepts a separate local key source, opens archives read-only and writes only inside this workspace. It never invokes UXM Patch/Restore or writes extracted files into the game installation.

The optional script uses the separately installed Python `cryptography` package and the user's own game-installed Oodle DLL for decompression in the research process. Those binaries are not redistributed. Raw extracted game assets stay in private research storage and must not be included in release archives. Output positions are candidate locations for constructed offline data, not captured player messages.

`tools/research-params` is another separate GPL-3.0-only developer tool. It uses externally supplied SoulsFormats and ZstdSharp libraries to read selected local regulation fields, plus separately obtained [Paramdex definitions](https://github.com/soulsmods/Paramdex/tree/master/ER/Defs). These dependencies and definitions are not installation requirements or bundled game components. No third-party research library is linked into the C++ replay DLL.

The separate GPL-3.0-only map research tools now also include `tools/research_mapinfo_archives.py` and `tools/research-params/MapInfoMasks.cs`. Their original BMP/binder inputs remain private. Public mapping summaries contain IDs/counts/hashes, not game textures. The static analysis helper permits a bounded private executable-section window of at most 16 KiB; it still has no process access, executable-memory allocation, runtime disabler or server requests.
