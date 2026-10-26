# Expanded snapshot installation

This is the **0.1.5 finite-snapshot stable release**: 23,439 authentic anonymous samples in 476 original map IDs. The frozen DLL passed Chinese/English UI readings, three title/death/travel/normal-restart rounds, and restored reading after natural native cache expiry. Both selected new records were read at their original positions in the full pack. This is neither a complete server dump nor a gap-free-world claim. See `verification/validation.json`.

Read `COVERAGE.json`, `data-provenance.json` and `verification/validation.json` for this archive's actual data and gameplay status. A sampled region, a map asset and a complete server dataset are different things. Preserve any development or incomplete-world labels when sharing.

The checked environment is Windows x64 Steam App 1.17.2 / Regulation 1.17.3, EXE 2.7.2.0, SHA-256 `F9118FEA2CFD8FA3901E8060BFADB1552CB2471771DED8A5B662C4E298FFB328`. Other images are refused. Install [ME3 0.13.0 from its official release](https://github.com/garyttierney/me3/releases/tag/v0.13.0) separately; neither ME3 nor game assets are bundled.

## Extract and launch

1. Extract the complete archive into a new folder, such as `E:\Mods\EROfflineMessages`. Keep the profile, launcher and `natives` layout. Do not overwrite the game or other mods.
2. Keep Steam running and exit the current game normally before replacing any loaded DLL.
3. On the tested host, run `Launch.cmd`. Elsewhere run `Launch.cmd "full path\me3.exe"`. The script uses an explicit loader, avoiding stale `.me3` associations.
4. Alternatively run `me3.exe launch --game eldenring --profile "full path\EROfflineMessages.me3"`. The profile enforces offline mode and selects no alternate save. Continue a vanilla-compatible character.
5. Keep `EROfflineMessages.pack.json` beside the DLL. Data is loaded once at startup. Wait several seconds after loading the character. Native spatial admission limits how many markers can appear together.

## Merge an existing profile

Make a separate copy, keep `start_online=false`, and add one `[[natives]]` entry pointing to this DLL. Retain its adjacent pack. Do not add duplicate or older replay DLLs. Other-mod compatibility requires separate testing; vanilla validation does not prove compatibility.

Set the existing top-level `start_online` field to `false`; do not add it inside a table. Append this native entry once, using the actual extracted location:

```toml
[[natives]]
path = 'E:\Mods\EROfflineMessages\natives\EROfflineMessages.dll'
```

## Data and languages

Normal-client and explicitly authorized independent-protocol cohorts have separate provenance. Installation data contains anonymous semantic fields, original positions, native phrase IDs and appraisal snapshots. No account IDs, tickets, names or appearance data are included. Ratings are neither live nor uploaded. Localization uses the native game text system; actual language checks remain version-specific.

The replay DLL has no collection or networking code. Developer collection tools are not part of installation. Do not add collection DLLs to the play profile or mix synthetic stress data into official snapshots.

## Troubleshooting and removal

Read `natives/EROfflineMessages.log`. `Loaded`, `Waiting` and `Registered` describe internal stages; they alone do not establish visible or readable messages. `Disabled` records a refusal. Exit normally and check the image, profile, pack and duplicate entries before replacing files. Do not edit saves or force-kill the game to clear a cache.

Check whether `COVERAGE.json` contains your map. Unsampled maps do not gain invented messages. Nearby selection and native density rules also affect visibility.

To uninstall, exit normally and stop using this profile, or remove its DLL entry from your copied profile. Restore your previous launch method. No game file was replaced and no tool directly edited saves. The game may autosave native message caches; leave cleanup to the game. Source/build instructions are in `source`, licenses in `licenses`, and per-file hashes in `SHA256SUMS.txt`.

## Verification scope and known limitations

- Simplified Chinese and English were compared on the same record, “don't give up!” /100. Other languages use native IDs but were not individually tested. Recovery rounds include user-confirmed readings; selected readings also have screenshots and native-field evidence.
- “Soldier ahead” /0 was readable in both the original-position single-record control and the full pack after loading at that position. Native density admission, nearest-object selection and entry position affect visibility. Cached/bound does not mean all records are readable simultaneously. No real record was relocated for testing.
- Three readable normal-restart rounds completed. An additional start before round 3 exited before gameplay for an unknown reason; no application crash event was found in the inspected time window. A subsequent start worked. This incomplete start is retained in `verification/release015-normal-restarts.json`; zero startup failures are not claimed.
- FPS/P99 comparisons and a one-hour soak were cancelled by the user. Quantified performance targets, long-term stability and other-mod compatibility are not claimed.
- Coverage is finite: 54 enabled region rows have no sample, some map associations remain unresolved, and the locked Jagged Peak Summit grace was not tested. No claim is made that every map or record was individually tested.
- The shipped DLL still logs the internal build label `0.1.5-dev1`: this is the frozen binary that passed these tests.

The final archive's DLL, data, profile and launcher are byte-identical to the tested extracted RC2. Only documentation/evidence changed during final packaging; rebuilding an archive is not counted as a fresh game launch test. External publication requires separate authorization. Platforms may quarantine DLL uploads; source, build instructions and SHA-256 hashes are supplied for review.
