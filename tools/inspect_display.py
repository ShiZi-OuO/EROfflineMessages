"""Anonymous, bounded offline display diagnostics; VM_READ only, no identity export."""
import argparse
import json
import math
from pathlib import Path
from observe import Reader

p=argparse.ArgumentParser()
p.add_argument('--output')
args=p.parse_args()
r=Reader()
try:
    snapshot=r.snapshot()
    player=r.u64(r.u64(r.base+0x3d6d018)+0x1e508)
    ctrl_owner=r.u64(r.u64(player+0x58)+0x10)
    physics=r.u64(r.u64(ctrl_owner+0x190)+0x68)
    position=r.unpack(physics+0x70,'<3f')
    origin=r.unpack(player+0x80,'<3f')
    db=int(snapshot['db'],16)
    result=dict(offline=snapshot['offline'],map=snapshot['map'],player_havok=position,
                block_origin=origin,managers=[])
    for offset in [0x60,0x68]:
        manager=r.u64(db+offset)
        ins=r.u64(manager+0x10)
        selected=r.u64(manager+0x30)
        records=[]
        visited=set()
        while ins:
            if ins in visited or len(visited)>=256:
                raise RuntimeError('Display chain exceeds bounded invariant')
            visited.add(ins)
            if r.u64(ins)!=r.base+0x29cd9e8:
                raise RuntimeError('Display instance vtable mismatch')
            xyz=r.unpack(ins+0x1c,'<3f')
            item=r.u64(ins+0x10)
            is_local=False
            if item:
                if r.u64(item)!=r.base+0x29cee88:
                    raise RuntimeError('Bound item vtable mismatch')
                is_local=r.u32(item+8)==0x7e000001
            # No external account keys, names, appearance or raw object dumps.
            record=dict(position=xyz,distance=math.dist(xyz,position),
                                constructed_local=is_local,selected=selected==ins,
                                display_flags=r.u32(ins+0x70)&0x3f)
            if item and selected==ins:
                phrase=r.unpack(item+0x2c,'<8H')
                record['message']=dict(map=r.u32(item+0x14),area=r.u32(item+0x48),
                    block_position=r.unpack(item+0x1c,'<3f'),template1=phrase[0],
                    word1=phrase[2],conjunction=phrase[3],template2=phrase[4],
                    word2=phrase[5],good=phrase[6],poor=phrase[7])
            records.append(record)
            ins=r.u64(ins+0x8c8)
        result['managers'].append(dict(kind='own' if offset==0x60 else 'others',
            interaction_state=r.u32(manager+0x38),instances=records))
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    if args.output:Path(args.output).write_text(text+'\n',encoding='utf-8')
    print(text)
finally:r.close()
