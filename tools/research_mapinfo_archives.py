# SPDX-License-Identifier: GPL-3.0-only
"""Read only map-info binders into private workspace research storage.

No network/process/save access. Never invokes a game patcher. Game bitmap
assets are private inputs, never Mod installation files.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from research_map_graces import EXPECTED_EXE,path_hash,decrypt_header,index_header,read_member,decompress


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('game','key-source','dictionary','output'):p.add_argument('--'+flag,required=True)
    a=p.parse_args();game=Path(a.game).resolve();root=Path(__file__).resolve().parents[1]
    output=Path(a.output).resolve()
    if not output.is_relative_to(root/'build/research') or output.exists():raise ValueError('New private workspace directory required')
    if hashlib.sha256((game/'eldenring.exe').read_bytes()).hexdigest()!=EXPECTED_EXE:raise ValueError('Exact image mismatch')
    source=Path(a.key_source).read_text(encoding='utf-8-sig').split('EldenRingKeys',1)[1].split('};',1)[0]
    keys=dict(re.findall(r'\["([^"]+)"\]\s*=\s*@"(-----BEGIN RSA PUBLIC KEY-----.*?-----END RSA PUBLIC KEY-----)"',source,re.S))
    paths={line.strip().lstrip('/') for line in Path(a.dictionary).read_text(encoding='utf-8-sig').splitlines()}
    paths={path for path in paths if re.fullmatch(r'other/mapinfotex/m(?:60|61)_\d\d_\d\d_02\.mapinfotexbnd\.dcx',path)}
    if not 1<=len(paths)<=256:raise ValueError('Map-info archive budget')
    wanted={path_hash(path):path for path in paths};found_paths=set();results=[];output.mkdir(parents=True)
    for archive in ['Data2','DLC','Data0','Data1','Data3']:
        header=decrypt_header((game/(archive+'.bhd')).read_bytes(),keys[archive]);found=index_header(header,wanted)
        print(f'{archive}: {len(found)} map-info binders',flush=True)
        with (game/(archive+'.bdt')).open('rb') as stream:
            for path,entry in found.items():
                raw=decompress(read_member(header,entry,stream),game)
                if raw[:4]!=b'BND4':raise ValueError('Expected BND4 map-info binder')
                filename=archive+'-'+Path(path).name.removesuffix('.dcx')
                (output/filename).write_bytes(raw);found_paths.add(path)
                results.append(dict(path=path,archive=archive,file=filename,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    (output/'index.json').write_text(json.dumps(dict(private_game_assets=True,files=results,missing=sorted(paths-found_paths)),indent=2)+'\n')
    print(f'{len(results)} binders, {len(paths-found_paths)} missing; no game or network writes',flush=True)


if __name__=='__main__':main()
