"""Capture one stationary offline player position as a synthetic fixture.

No official message collection, identity fields, memory writes or save access.
"""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from observe import Reader

p=argparse.ArgumentParser()
p.add_argument('--output',required=True)
p.add_argument('--append-pack')
p.add_argument('--good',type=int,default=19)
p.add_argument('--poor',type=int,default=4)
p.add_argument('--template',type=int,default=10000)
p.add_argument('--word',type=int,default=32003)
a=p.parse_args()
if not all(0<=v<=9999 for v in [a.good,a.poor]):raise ValueError('Rating bounds')
if not 1<=a.template<=65535 or not 0<=a.word<=65535:raise ValueError('Text ID bounds')
reader=Reader()
try:
    first=reader.snapshot()
    time.sleep(1)
    s=reader.snapshot()
    if first['map']!=s['map'] or math.dist(first['position_candidate'],s['position_candidate'])>.05:
        raise RuntimeError('Stand still in a loaded area before capturing a point')
    player=reader.u64(reader.u64(reader.base+0x3d6d018)+0x1e508)
    if reader.u32(player+0x30)!=int(s['map'],16):raise RuntimeError('Player map mismatch')
    origin=reader.unpack(player+0x80,'<3f')
    owner=reader.u64(reader.u64(player+0x58)+0x10)
    physics=reader.u64(reader.u64(owner+0x190)+0x68)
    actual=reader.unpack(physics+0x70,'<3f')
    if math.dist(actual,s['position_candidate'])>.05:raise RuntimeError('Position representations disagree')
    position=[v-o for v,o in zip(actual,origin)]
    if not all(math.isfinite(v) and abs(v)<1e6 for v in position):raise ValueError('Coordinate bounds')
    record=dict(map=int(s['map'],16),area=s['region'],secondary_area=0,position=position,
        yaw=s['yaw_candidate'],template1=a.template,word1=a.word,conjunction=0,template2=0,
        word2=0,good=a.good,poor=a.poor)
    record['id']='7e'+hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:14]
    if a.append_pack:
        data=json.loads(Path(a.append_pack).read_text(encoding='utf-8'))
        if data.get('source_type')!='constructed' or data.get('game')!='eldenring':raise ValueError('Only append to a constructed pack')
    else:
        data=dict(schema_version=1,game='eldenring',source_type='constructed',messages=[])
    if any(item['id']==record['id'] for item in data['messages']):raise ValueError('Duplicate synthetic point')
    data['messages'].append(record)
    data['description']='Synthetic offline fixtures at stationary offline-observed player positions. Native phrase IDs; terrain and readability require separate visual testing. Zero official player samples.'
    Path(a.output).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=a.output,map=s['map'],block_local=position,expected_total=a.good+a.poor,visual_test='required'),indent=2))
finally:reader.close()
