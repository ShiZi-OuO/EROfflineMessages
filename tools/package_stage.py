"""Preserve a runnable, explicitly incomplete milestone; never publish anything."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parent.parent
destination=root/'dist'/'EROfflineMessages-0.1.1-readability-milestone'
destination.mkdir(parents=True,exist_ok=False)
(destination/'natives').mkdir()
shutil.copy2(root/'build/bin/Release/EROfflineMessages.dll',destination/'natives')
shutil.copy2(root/'data/fixture-A.json',destination/'natives/EROfflineMessages.pack.json')
(destination/'EROfflineMessages.me3').write_text('''profileVersion = "v1"
start_online = false
disable_arxan = false
mem_patch = false

[[supports]]
game = "eldenring"

[[natives]]
path = 'natives/EROfflineMessages.dll'
''',encoding='utf-8')
(destination/'Launch.cmd').write_text('''@echo off
setlocal
set "ER_ME3=%~1"
if not defined ER_ME3 set "ER_ME3=F:\\Steam\\steamapps\\common\\ELDEN RING\\Game\\bin\\me3.exe"
if not exist "%ER_ME3%" (
  echo Usage: Launch.cmd "full path to me3.exe"
  exit /b 1
)
tasklist /FI "IMAGENAME eq eldenring.exe" /NH | findstr /I /C:"eldenring.exe" >nul
if not errorlevel 1 (
  echo Exit Elden Ring normally before launching this profile.
  exit /b 1
)
"%ER_ME3%" launch --game eldenring --profile "%~dp0EROfflineMessages.me3"
exit /b %errorlevel%
''',encoding='ascii',newline='\r\n')
(destination/'README.zh-CN.md').write_text('''# 离线谏言 0.1.1 阅读验证里程碑

这是供本次开发验证使用的阶段构建，**不是正式成品**。当前仅有艾雷教堂附近的一条构造谏言，官方玩家样本为 0。其他地图没有随包配置谏言。

已实测：EXE 2.7.2.0（Steam App 1.17.2 / Regulation 1.17.3），ME3 0.13.0，原版环境，简体中文地面标记及阅读界面；文字“前有重要的道具”，总评价 10。返回标题、传送往返与死亡复活的各轮结果详见 verification/validation.json。英语、长期运行、密集数据及帧率对比尚未完成验收。

## 安装与启动

1. 将整个目录解压到一个新的独立文件夹，例如 E:\\Mods\\EROfflineMessages。不要覆盖游戏文件、其他 Mod 或旧备份。
2. 保持 Steam 运行，并通过游戏菜单正常退出当前游戏。
3. 使用 ME3 0.13.0。当前机器可双击 Launch.cmd；其他位置用命令 `Launch.cmd "你的完整路径\\me3.exe"`。
4. 本配置强制脱机、不加载其他资源或 DLL、不指定替代存档。继续现有原版角色，到艾雷教堂赐福附近寻找测试标记。游戏自身仍正常自动保存和维护缓存；本工具不直接编辑存档文件。

也可直接运行 `me3.exe launch --game eldenring --profile "本目录\\EROfflineMessages.me3"`，务必使用明确的 ME3 路径，避免旧版 .me3 文件关联。

## 合并、排错与卸载

合并已有配置前先复制一份到新目录，只增加一次 `[[natives]]` 条目，路径指向本包的 natives/EROfflineMessages.dll，保留 DLL 旁的数据文件。保持 `start_online=false`。本阶段尚未验收其他 Mod 的兼容性；当前验证使用独立配置。

日志在 natives/EROfflineMessages.log。Loaded 表示 DLL 已载入，Ready 表示脱机检查通过，Registered 表示已登记，均不能单独证明可见或可读。Disabled 会说明停止原因。游戏版本不匹配、数据损坏或反作弊进程存在时会拒绝回放。数据只在启动时读取；更换 DLL 或数据前正常退出游戏。

卸载：正常退出游戏，停止使用该配置，恢复原来独立保存的启动方式。该文件夹可保留或自行移除；没有替换游戏原文件。原版缓存可能短暂保留测试记录，清理由游戏执行，不要为此编辑存档。

源码在 source/；构建步骤在 source/docs/BUILD.md；第三方许可在 licenses/；逐文件校验值在 SHA256SUMS.txt。本包不包含 ME3 或游戏资源。请勿将该阶段构建描述为完成全部验收的正式版。
''',encoding='utf-8')
(destination/'README.en.md').write_text('''# Offline Messages 0.1.1 readability milestone

This is an incomplete development milestone, not a finished release. It contains one synthetic fixture near the Church of Elleh and zero official player samples. Other maps have no bundled fixtures.

Verified environment: EXE 2.7.2.0, Steam App 1.17.2 / Regulation 1.17.3, ME3 0.13.0, separate vanilla profile. The original ground marker and Chinese reading UI display the fixture with total appraisals 10. See verification/validation.json for lifecycle results and remaining checks. English, one-hour stability and comparative FPS have not passed acceptance.

Extract the complete directory into a new folder, e.g. E:\\Mods\\EROfflineMessages. Keep Steam running and exit the current game normally. Launch with `Launch.cmd "full path to me3.exe"` using ME3 0.13.0. On the tested host the launcher defaults to the existing game installation's bin/me3.exe. Alternatively run the explicit loader with `launch --game eldenring --profile "full path to EROfflineMessages.me3"`.

The profile sets start_online=false, loads only this DLL, and selects no alternate save file. Continue a vanilla character and visit the Church of Elleh. Normal game autosaving and native cache maintenance still occur; no tool directly edits save files. Do not overwrite game files, other profiles or backups.

To merge with an existing profile, first make a separate copy. Add the natives/EROfflineMessages.dll entry exactly once, retain its adjacent pack file, and keep start_online=false. Compatibility with other mods is unverified.

Logs are written next to the DLL. Loaded, Ready and Registered indicate different internal stages; they do not by themselves prove visible or readable messages. Disabled reports a safety refusal. The data file is loaded once at startup. Exit normally before replacing DLLs or data.

To uninstall, exit normally and stop using this profile; restore your previous launch method. No original game file was replaced. Native cached test records are left to the game's cleanup; do not edit saves to remove them.

Source and build instructions are in source/, licenses in licenses/, measured status in verification/, and per-file hashes in SHA256SUMS.txt. ME3 and game assets are not bundled. The standalone milestone launcher still requires an installation test.
''',encoding='utf-8')
source=destination/'source'
for directory in ['src','tests','third_party','data','profiles']:
    shutil.copytree(root/directory,source/directory)
for file in ['CMakeLists.txt','README.md','THIRD_PARTY.md']:
    shutil.copy2(root/file,source/file)
for file in ['BUILD.md','DATA_FORMAT.md']:
    (source/'docs').mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/'docs'/file,source/'docs'/file)
(source/'tools').mkdir()
for file in (root/'tools').glob('*.py'):shutil.copy2(file,source/'tools'/file.name)
shutil.copy2(root/'tools/launch-dev.ps1',source/'tools')
(destination/'licenses').mkdir()
shutil.copy2(root/'third_party/minhook/LICENSE.txt',destination/'licenses/MinHook.txt')
shutil.copy2(root/'third_party/json/LICENSE.MIT',destination/'licenses/nlohmann-json.txt')
shutil.copy2(root/'THIRD_PARTY.md',destination/'licenses/THIRD_PARTY.md')
(destination/'verification').mkdir()
for name in ['validation.json','v011-A-readable-zh.png','v011-A-after-title-teleport-zh.png','v011-A-after-title-teleport-native.json']:
    shutil.copy2(root/'evidence'/name,destination/'verification'/name)
files=sorted(p for p in destination.rglob('*') if p.is_file())
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(destination).as_posix()+'\n' for p in files)
(destination/'SHA256SUMS.txt').write_text(manifest,encoding='utf-8')
archive=destination.parent/(destination.name+'.zip')
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for file in sorted(destination.rglob('*')):
        if file.is_file():z.write(file,file.relative_to(destination.parent))
with zipfile.ZipFile(archive) as z:
    if z.testzip():raise RuntimeError('ZIP CRC failure')
print(json.dumps(dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(files)+1,release_ready=False),indent=2))
