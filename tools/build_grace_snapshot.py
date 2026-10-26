"""Build a conservative constructed snapshot; never classifies it as player data."""
import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--maps',required=True);p.add_argument('--params',required=True)
p.add_argument('--output',required=True);p.add_argument('--provenance',required=True);a=p.parse_args()
root=Path(__file__).resolve().parent.parent
maps=json.loads(Path(a.maps).read_text(encoding='utf-8'))['maps']
params=json.loads(Path(a.params).read_text(encoding='utf-8'))['parameters']
warps={r['fields']['bonfireEntityId']:r for r in params['BonfireWarpParam']['rows']}
regions={r['id']:r['fields']['enableBloodMessage'] for r in params['PlayRegionParam']['rows']}
records=[];origins=[];used_entities=set();excluded=collections.Counter()

def add(record,origin):
    record={k:v for k,v in record.items() if k!='id'}
    record.update(template1=10000,word1=32032,conjunction=0,template2=0,word2=0,good=0,poor=0)
    record['id']='7e'+hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:14]
    records.append(record);origins.append(dict(local_key=record['id'],**origin))

# Retain the two exact placement coordinates already read successfully in game.
for record in json.loads((root/'data/fixture-two-maps.json').read_text(encoding='utf-8'))['messages']:
    add(record,dict(origin='offline_game_verified_placement',position_verified=True,
        new_phrase_reading_verified=False,note='Position read on 0.1.1/0.1.2; grace phrase is a new constructed record'))
used_entities.update([1042361950,30021950])
for m in maps:
    match=re.search(r'm(\d\d)_(\d\d)_(\d\d)_(\d\d)\.msb',m['path'])
    if not match:raise ValueError('Map filename')
    source_map=tuple(map(int,match.groups()))
    for asset in m['grace_asset_candidates']:
        entity=asset['entity_id']
        if entity in used_entities:continue
        warp=warps.get(entity)
        if not warp:excluded['no_matching_warp_entity']+=1;continue
        linked={r['play_region_id'] for r in asset['related_parts'] if r.get('play_region_id',0)>0}
        if len(linked)!=1:excluded['no_unique_direct_collision_region']+=1;continue
        region=next(iter(linked))
        if regions.get(region)!=1:excluded['region_does_not_enable_messages']+=1;continue
        # Parent-world transforms require more area evidence; keep them out of this set.
        if source_map[3]!=0 or asset['part_name'].startswith('m'):
            excluded['world_parent_transform_not_admitted']+=1;continue
        if source_map[:3]!=(warp['fields']['areaNo'],warp['fields']['gridXNo'],warp['fields']['gridZNo']):
            excluded['warp_map_and_asset_map_differ']+=1;continue
        yaw=math.radians(asset['rotation_degrees'][1])
        position=list(asset['position'])
        position[0]+=math.sin(yaw)*1.25;position[2]+=math.cos(yaw)*1.25;position[1]+=.03
        mapid=int.from_bytes(bytes(source_map),'big')
        record=dict(map=mapid,area=region,secondary_area=0,position=position,yaw=yaw)
        add(record,dict(origin='constructed_near_original_grace_asset',grace_entity=entity,
            warp_row=warp['id'],source_map=m['path'],source_archive=m['archive'],msb_sha256=m['msb_sha256'],
            asset_position=asset['position'],placement_offset_metres=1.25,area_basis='unique directly linked collision PlayRegionID with enableBloodMessage=1',
            position_verified=False,new_phrase_reading_verified=False,
            note='Static map evidence only; floor and reading at this offset are not individually game-tested'))
        used_entities.add(entity)
counts=collections.Counter(r['map'] for r in records)
if max(counts.values(),default=0)>96:raise ValueError('Per-map replay budget exceeded')
if len({r['id'] for r in records})!=len(records):raise ValueError('Duplicate synthetic ID')
data=dict(schema_version=1,game='eldenring',source_type='constructed',
    description='Constructed fixed snapshot near original grace assets, not official player messages. Native template 10000 / word 32032, test appraisals zero. Two placement coordinates were game-verified; additional offsets have static asset/collision evidence and require gameplay sampling. No full-world or per-point validation claim.',messages=records)
provenance=dict(schema_version=1,official_player_samples=0,constructed_records=len(records),maps=len(counts),maximum_records_per_map=max(counts.values()),
    original_game_sha256='F9118FEA2CFD8FA3901E8060BFADB1552CB2471771DED8A5B662C4E298FFB328',
    phrase=dict(template=10000,word=32032,native_combined_text_id=10032032,source='local original localization, not hardcoded sentences'),
    ratings='All zero; constructed test values, no real player appraisals',excluded_candidates=dict(excluded),records=origins)
for name,value in [(a.output,data),(a.provenance,provenance)]:
    path=Path(name).resolve()
    if not path.is_relative_to(root) or path.exists():raise ValueError('Use new workspace output files')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
print(json.dumps({k:provenance[k] for k in ['constructed_records','maps','maximum_records_per_map','excluded_candidates']},indent=2))
