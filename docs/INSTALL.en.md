# Elden Ring Offline Messages 0.1.3 — finite client-received snapshot

This package replays **103 records received through a normal official client** using the native ground marker, interaction prompt and reading UI: 41 in Groveside Cave and 62 in nearby open-world block m60_42_37_00. It is not a complete server dataset or full-world coverage. One record has individual online/offline text, appraisal and placement correspondence. Version-specific sampled tests are recorded in `verification/validation.json`.

The snapshot preserves received block-local positions, regions, native template/word IDs and appraisal totals. The game supplies localization; 17 records have two phrases. Account IDs, names, appearance, gestures and phantoms are omitted. Appraisals are never uploaded. Constructed fixtures remain separately labelled under `source/data/` and are not part of the default runtime pack.

## Install and launch

1. Use the Steam game with a separately installed **ME3 0.13.0**; the loader is not bundled. The checked game is App 1.17.2 / Calibrations 1.17.3, EXE 2.7.2.0, SHA-256 `F9118FEA2CFD8FA3901E8060BFADB1552CB2471771DED8A5B662C4E298FFB328`. Other images are refused.
2. Extract the entire package into a new folder, such as `E:\Mods\EROfflineMessages`. It need not be in Game. Do not overwrite game files, other mods, existing profiles or backups.
3. Keep Steam running and exit the current game normally. Run `Launch.cmd`. Its default explicit loader path is `F:\Steam\steamapps\common\ELDEN RING\Game\bin\me3.exe`, avoiding stale file associations.
4. For another loader location, run `Launch.cmd "C:\your path\me3.exe"` or edit the script's default. Alternatively invoke the loader's full path with `launch --game eldenring --profile "full package path\EROfflineMessages.me3"`.
5. Confirm the title is offline, then continue a vanilla character. This profile loads only this DLL, no replacement assets or alternate save. Look in Groveside Cave or its nearby outside block and allow several seconds for registration. Use the game's action-switch prompt if interactions overlap.

Do not use `start_protected_game.exe` to load this replay profile. Replay refuses or pauses when EAC is present or offline conditions cannot be established. Let the original protected client exit normally; do not alter anti-cheat files or disable security software to bypass a refusal. No tool directly edits saves; ordinary game autosaving and native cache persistence still occur.

## Merge an existing profile

Make a separate copy first. Keep `start_online = false` and add exactly one entry using the actual absolute DLL path:

```toml
[[natives]]
path = 'E:\Mods\EROfflineMessages\natives\EROfflineMessages.dll'
```

Retain the adjacent `EROfflineMessages.pack.json`. Do not load a second copied DLL through another profile. A process-wide guard rejects duplicate instances, but the profile should still contain only one entry. Other-mod compatibility is unverified; gameplay testing uses a separate vanilla profile.

## Logs and troubleshooting

The log is `natives/EROfflineMessages.log`. Loaded, Ready and Registered are separate internal stages, not proof of visibility/readability. Disabled supplies a refusal reason. Keep image/signature checks intact.

- No log: check the explicit ME3 path, DLL path and directory write permission.
- Ready without markers: check two-map coverage, allow stable loading and registration, and remember native density admission can display fewer markers than cached records.
- CacheBudget: the Mod's cache budget is full. Version 0.1.3 retries at most once per second and resumes after native cleanup. It does not delete game-owned nodes. Recent online gameplay can leave old cache entries; cleanup timing belongs to the game. Do not edit saves to clear them.
- Bad data: restore the original JSON. Unknown fields, duplicate local message IDs and invalid coordinates are rejected. The pack loads once at startup.
- Exit normally before replacing DLLs or data. Hot unload/replacement is unsupported.

## Remove, verify and build

Exit normally, stop using this profile and restore your previous launch method. You may then remove this separate directory; no original game file was replaced. If merged, remove only this Mod's entry from the copied profile. Leave old replay cache to native cleanup; do not edit saves to remove it.

Per-file SHA-256 hashes are in `SHA256SUMS.txt`. Use `Get-FileHash .\natives\EROfflineMessages.dll -Algorithm SHA256` in PowerShell to compare the DLL; the archive digest is supplied separately as `.zip.sha256`. Complete source and offline build instructions are under `source/`; licenses are in `licenses/`. Only the game and separate ME3 installation are play dependencies. Python, .NET and research libraries are optional developer tools. Raw game assets/text tables, private cache observations and proxy backups are excluded.

## Evidence limits

See `verification/TEST_REPORT.md` and the machine-readable record, which separate versions 0.1.1, 0.1.2 and 0.1.3. One real sample completed online reading, normal exit, offline extraction and native replay reading with matching text and total. Other records share collection provenance but are not all individually witnessed. Support claims cover only the checked image and actual recorded tests.

The user cancelled further performance and one-hour stability testing. No FPS/P99 target or one-hour pass is claimed. Do not infer additional language coverage, other-mod compatibility or untested map coverage. Replay remains offline and sends no update/appraisal requests.

The current 0.1.3 binary has actual Chinese/English native double-phrase reading evidence. English was tested from an extracted ZIP installation. The test user confirmed title/continue and death recovery, three rounds each. Final runtime files are hash-matched to that tested payload.
