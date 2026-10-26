"""Build an immutable local expansion archive from explicitly chosen artifacts.

No upload, game launch, credentials, private build research or approvals. This
tool never upgrades validation claims simply because packaging succeeds.
"""
import argparse
import collections
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path
from merge_official_packs import merge

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('tag','dll','pack','provenance','validation','build-manifest'):p.add_argument('--'+flag,required=True)
    p.add_argument('--evidence',action='append',default=[])
    a=p.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,90}',a.tag):raise ValueError('Archive tag')
    load=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    pack=load(a.pack);merge([pack])  # Core anonymous semantic validation.
    provenance=load(a.provenance);validation=load(a.validation)
    digest=hashlib.sha256(Path(a.dll).read_bytes()).hexdigest()
    build=load(a.build_manifest)
    if build['dll_sha256'].lower()!=digest:raise ValueError('Wrong build/source manifest for binary')
    for name,expected in build['source_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Runtime source no longer corresponds to chosen binary: '+name)
    if validation['dll_sha256'].lower()!=digest or provenance['runtime_pack_sha256']!=hashlib.sha256(Path(a.pack).read_bytes()).hexdigest():
        raise ValueError('Binary/data validation digest mismatch')
    if validation.get('full_world_coverage',False)!=provenance.get('full_world_coverage',False):
        raise ValueError('Coverage claims disagree')
    for path in a.evidence:
        path=Path(path).resolve()
        if path.parent!=ROOT/'evidence' or path.suffix not in ('.json','.png','.jpg','.md') or 'authorization' in path.name:
            raise ValueError('Public evidence allowlist; never bundle approvals/private inputs')
    dest=ROOT/'dist'/('EROfflineMessages-'+a.tag)
    archive=dest.parent/(dest.name+'.zip')
    if dest.exists() or archive.exists():raise ValueError('Immutable new package destination required')
    (dest/'natives').mkdir(parents=True)
    shutil.copy2(a.dll,dest/'natives/EROfflineMessages.dll')
    shutil.copy2(a.pack,dest/'natives/EROfflineMessages.pack.json')
    shutil.copy2(a.provenance,dest/'data-provenance.json')
    maps=collections.Counter(r['map'] for r in pack['messages'])
    coverage=dict(records=len(pack['messages']),source_type=pack['source_type'],
        maps={'m'+'_'.join(f'{b:02d}' for b in m.to_bytes(4,'big')):n for m,n in sorted(maps.items())},
        full_world_coverage=provenance.get('full_world_coverage',False),
        warning='Finite snapshot. Sample presence does not prove whole-region or full-server coverage.')
    (dest/'COVERAGE.json').write_text(json.dumps(coverage,indent=2)+'\n')
    for language in ('zh-CN','en'):shutil.copy2(ROOT/f'docs/INSTALL.world.{language}.md',dest/f'README.{language}.md')
    for name in ('EROfflineMessages.me3','Launch.cmd'):shutil.copy2(ROOT/'packaging'/name,dest/name)
    source=dest/'source';ignore=shutil.ignore_patterns('__pycache__','local','bin','obj','target','*.pyc')
    for name in ('src','tests','third_party','data','profiles','docs','licenses','tools','packaging'):
        shutil.copytree(ROOT/name,source/name,ignore=ignore)
    for name in ('CMakeLists.txt','README.md','THIRD_PARTY.md','.gitignore'):shutil.copy2(ROOT/name,source/name)
    licences=dest/'licenses';licences.mkdir()
    for name,original in [('MinHook.txt','third_party/minhook/LICENSE.txt'),('nlohmann-json.txt','third_party/json/LICENSE.MIT'),
                          ('THIRD_PARTY.md','THIRD_PARTY.md'),('research-tools-GPL-3.0.txt','licenses/research-tools-GPL-3.0.txt')]:
        shutil.copy2(ROOT/original,licences/name)
    verification=dest/'verification';verification.mkdir()
    shutil.copy2(a.validation,verification/'validation.json')
    shutil.copy2(a.build_manifest,verification/'build-source-manifest.json')
    for path in a.evidence:shutil.copy2(path,verification/Path(path).name)
    files=sorted(p for p in dest.rglob('*') if p.is_file())
    (dest/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(dest).as_posix()+'\n' for p in files),encoding='utf-8')
    pending=archive.with_name(archive.name+'.pending')
    with zipfile.ZipFile(pending,'x',zipfile.ZIP_DEFLATED,strict_timestamps=False) as z:
        for path in sorted(dest.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(dest.parent))
    with zipfile.ZipFile(pending) as z:
        if z.testzip():raise RuntimeError('Archive CRC failure')
    pending.rename(archive)
    sha=hashlib.sha256(archive.read_bytes()).hexdigest()
    (archive.parent/(archive.name+'.sha256')).write_text(sha+'  '+archive.name+'\n')
    print(json.dumps(dict(archive=str(archive),sha256=sha,records=coverage['records'],
        game_test_status=validation.get('pack_gameplay_status','unverified'),full_world_coverage=coverage['full_world_coverage'])))


if __name__=='__main__':main()
