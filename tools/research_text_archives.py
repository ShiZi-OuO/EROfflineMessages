# SPDX-License-Identifier: GPL-3.0-only
"""Extract an allowlisted set of local message binders to private research storage.

Never modifies archives, EXE, saves, or a running client. No network requests.
Raw game text binders are not release assets.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from research_map_graces import EXPECTED_EXE,path_hash,decrypt_header,index_header,read_member,decompress

p=argparse.ArgumentParser();p.add_argument('--game',required=True);p.add_argument('--key-source',required=True)
p.add_argument('--member',action='append',required=True);p.add_argument('--output',required=True);a=p.parse_args()
game=Path(a.game).resolve();root=Path(__file__).resolve().parent.parent
output=Path(a.output).resolve()
if not output.is_relative_to(root/'build/research') or output.exists():raise ValueError('Use a new private build/research output directory')
if not 1<=len(a.member)<=24 or any(not re.fullmatch(r'msg/(engus|zhocn)/(item|menu)(?:_dlc0[12])?\.msgbnd\.dcx',v) for v in a.member):raise ValueError('Message binder allowlist')
if hashlib.sha256((game/'eldenring.exe').read_bytes()).hexdigest()!=EXPECTED_EXE:raise ValueError('Game image mismatch')
source=Path(a.key_source).read_text(encoding='utf-8-sig').split('EldenRingKeys',1)[1].split('};',1)[0]
keys=dict(re.findall(r'\["([^"]+)"\]\s*=\s*@"(-----BEGIN RSA PUBLIC KEY-----.*?-----END RSA PUBLIC KEY-----)"',source,re.S))
missing={path_hash(v):v for v in a.member};result=[];output.mkdir(parents=True)
for archive in ['Data3','Data0','Data1','Data2','DLC']:
    if not missing:break
    header=decrypt_header((game/(archive+'.bhd')).read_bytes(),keys[archive]);found=index_header(header,missing)
    print(f'{archive}: {len(found)} message binders',flush=True)
    with (game/(archive+'.bdt')).open('rb') as stream:
        for member,entry in found.items():
            data=decompress(read_member(header,entry,stream),game)
            if data[:4]!=b'BND4':raise ValueError('Expected BND4 message binder')
            destination=output/member;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
            result.append(dict(member=member,archive=archive,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
            del missing[path_hash(member)]
(output/'index.json').write_text(json.dumps(dict(source='local game resources, private research only; no player samples',files=result,missing=list(missing.values())),indent=2)+'\n',encoding='utf-8')
if missing:raise RuntimeError('Some selected text binders not found')
