"""Synthetic, separate performance fixtures. Not official samples or world coverage."""
import copy
import argparse
import hashlib
import json
import math
from pathlib import Path

root=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--anchor-pack',default=str(root/'data/fixture-A.json'));p.add_argument('--record-index',type=int,default=0);p.add_argument('--prefix',default='');p.add_argument('--compact',action='store_true');a=p.parse_args()
base=json.loads(Path(a.anchor_pack).read_text(encoding='utf-8'))
anchor=copy.deepcopy(base['messages'][a.record_index])
output=root/'data/performance'
output.mkdir(exist_ok=True)
for name,count,spacing in [('normal-8',8,1.4),('stress-88',88,.7)]:
    name=a.prefix+name
    if a.compact:spacing=.12
    data=copy.deepcopy(base)
    data['description']=f'Synthetic {name} performance fixture only. Positions form a planar test grid near anchor map {anchor["map"]:#010x}; terrain at every point is not validated. Native density admission may display fewer records than cached. Not official messages, not a general gameplay data pack.'
    data['messages']=[]
    side=math.ceil(math.sqrt(count))
    for n in range(count):
        record=copy.deepcopy(anchor)
        record['position'][0]+=(n%side-(side-1)/2)*spacing
        record['position'][2]+=(n//side-(side-1)/2)*spacing
        record['good']=n%17+1
        record['poor']=n%3
        semantic={k:v for k,v in record.items() if k!='id'}
        semantic['test_purpose']=name
        record['id']='7e'+hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:14]
        data['messages'].append(record)
    path=output/(name+'.json')
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{name}: {count} constructed records, {path.name}')
