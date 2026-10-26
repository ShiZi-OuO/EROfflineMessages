"""Create a local, immutable install ZIP. Never uploads or publishes."""
import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a=p.parse_args()
if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,90}',a.tag):raise ValueError('Package tag')
root=Path(__file__).resolve().parent.parent
destination=root/'dist'/('EROfflineMessages-'+a.tag)
destination.mkdir(parents=True,exist_ok=False)
(destination/'natives').mkdir()
shutil.copy2(root/'build/bin/Release/EROfflineMessages.dll',destination/'natives')
shutil.copy2(root/'data/official-snapshot-103.json',destination/'natives/EROfflineMessages.pack.json')
shutil.copy2(root/'data/official-snapshot-103.provenance.json',destination/'data-provenance.json')
shutil.copy2(root/'docs/COVERAGE.official.md',destination/'COVERAGE.md')
for language in ['zh-CN','en']:shutil.copy2(root/f'docs/INSTALL.{language}.md',destination/f'README.{language}.md')
shutil.copy2(root/'packaging/EROfflineMessages.me3',destination/'EROfflineMessages.me3')
shutil.copy2(root/'packaging/Launch.cmd',destination/'Launch.cmd')
source=destination/'source'
ignore=shutil.ignore_patterns('__pycache__','local','bin','obj','*.pyc')
for name in ['src','tests','third_party','data','profiles','docs','licenses','tools','packaging']:
    shutil.copytree(root/name,source/name,ignore=ignore)
for name in ['CMakeLists.txt','README.md','THIRD_PARTY.md','.gitignore']:shutil.copy2(root/name,source/name)
licenses=destination/'licenses';licenses.mkdir()
for name,path in [('MinHook.txt','third_party/minhook/LICENSE.txt'),('nlohmann-json.txt','third_party/json/LICENSE.MIT'),('THIRD_PARTY.md','THIRD_PARTY.md'),('research-tools-GPL-3.0.txt','licenses/research-tools-GPL-3.0.txt')]:shutil.copy2(root/path,licenses/name)
verification=destination/'verification';verification.mkdir()
for name in ['validation.json','TEST_REPORT.md','source-archive-rebuild.json','source-archive-rebuild-v013.json',
             'official-client-pilot.json','official-client-online-title.png',
             'official-client-group7-online.png','official-pilot-offline-title.png',
             'official-pilot-empty-control.json','official-pilot-replay-display.json',
             'official-pilot-group7-offline-readable.png','official-pilot-v012-runtime.log',
             'official103-v013-readable-zh.png','official103-v013-readable-en.png',
             'official103-v013-outside-readable-zh.png','official103-v013-validation.json',
             'official103-v013-runtime.log','official103-v013-installed-runtime.log','official103-v013-cache-recovery.json','official103-localization-static.json',
             'v011-A-readable-zh.png','v011-B-readable-zh.png','v011-B-readable-en.png',
             'v011-A-after-cache-expiry-zh.png','v012-interior-readable-zh.png',
             'snapshot40-groveside-readable-zh.png','snapshot40-readable-en.png',
             'cancelled-soak-summary.json','runtime-dependencies.json',
             'map-anchor-comparison.json','stress-v012-timings.json']:
    path=root/'evidence'/name
    if path.exists():shutil.copy2(path,verification/name)
files=sorted(p for p in destination.rglob('*') if p.is_file())
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(destination).as_posix()+'\n' for p in files)
(destination/'SHA256SUMS.txt').write_text(manifest,encoding='utf-8')
archive=destination.parent/(destination.name+'.zip')
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for path in sorted(destination.rglob('*')):
        if path.is_file():z.write(path,path.relative_to(destination.parent))
with zipfile.ZipFile(archive) as z:
    if z.testzip():raise RuntimeError('ZIP CRC failure')
status=json.loads((root/'evidence/validation.json').read_text(encoding='utf-8'))
result=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(files)+1,
            release_ready=status['release_ready'],acceptance_scope=status.get('acceptance_scope','incomplete'))
(archive.parent/(archive.name+'.sha256')).write_text(result['sha256']+'  '+archive.name+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
