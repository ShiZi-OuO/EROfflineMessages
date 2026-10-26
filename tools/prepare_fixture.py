"""Create clearly synthetic A/B data near an offline player's observed position.
Uses only the offline read observer; writes project data, never game memory or saves.
"""
import json
import hashlib
from pathlib import Path
from observe import Reader

root=Path(__file__).resolve().parent.parent
r=Reader()
try:
    snapshot=r.snapshot()
    # Verified 2.7.2.0: NetMan+0x28 is Havok position, not block-local.
    # BloodMessageData+0x1c is block-local; native receive adds ChrIns+0x80.
    player=r.u64(r.u64(r.base+0x3d6d018)+0x1e508)
    if r.u32(player+0x30)!=int(snapshot['map'],16):
        raise RuntimeError('Player block does not match NetMan; fixture refused')
    origin=r.unpack(player+0x80,'<3f')
    position=[v-o for v,o in zip(snapshot['position_candidate'],origin)];position[0]+=2
    record=dict(id='7e000000000f0001',map=int(snapshot['map'],16),area=snapshot['region'],secondary_area=0,position=position,yaw=snapshot['yaw_candidate'],template1=10000,word1=32003,conjunction=0,template2=0,word2=0,good=7,poor=3)
    data=dict(schema_version=1,game='eldenring',source_type='constructed',description='Synthetic offline A/B test; native phrase IDs from observed cached records, newly chosen position and ratings. Not an official player message.',messages=[record])
    for variant in ['A','B']:
        if variant=='B':record.update(id='7e000000000f0002',template1=10004,word1=30015,good=11,poor=2)
        # A changed fixture must not collide with a previous native cache entry.
        semantic={k:v for k,v in record.items() if k!='id'}
        record['id']='7e'+hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()[:14]
        (root/'data'/f'fixture-{variant}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (root/'build'/'bin'/'Release'/'EROfflineMessages.pack.json').write_bytes((root/'data'/'fixture-A.json').read_bytes())
    print(json.dumps(dict(source='constructed',map=snapshot['map'],area=snapshot['region'],block_origin=origin,block_local_position=position,expected_havok_position=[v+o for v,o in zip(position,origin)],expected_appraisals_A=10,expected_appraisals_B=13),indent=2))
finally:r.close()
