"""Prepare, never execute, grouped queries for newly derived world targets.

The native ABI accepts a vector. Server-side coverage/capping of multi-area
replies remains unverified; missing targets need individually bounded fallback.
"""
import argparse
import hashlib
import json
from pathlib import Path


def build(previous, expanded, known_asset_maps=None):
    existing={t['id'] for t in previous['targets']}
    new=[t for t in expanded['targets'] if t['id'] not in existing]
    if len({tuple(t['pair']) for t in new})!=len(new):raise ValueError('Duplicate new target')
    controls=[]
    for pair in ([3103001,3103001],[6042370,6100002],[3002001,3002001]):
        matches=[t for t in previous['targets'] if t['pair']==pair]
        if len(matches)!=1:raise ValueError('Known control target missing')
        controls.append(matches[0])
    if set(t['id'] for t in controls)&set(t['id'] for t in new):raise ValueError('Controls cannot be new targets')
    groups=[dict(id=f'world-group-{n//8+1:03d}',target_ids=[t['id'] for t in new[n:n+8]]) for n in range(0,len(new),8)]
    return dict(schema_version=1,status='PREPARED_NOT_AUTHORIZED',server_group_queries_tested=False,
        native_vector_shape_only_verified=True,new_target_count=len(new),targets=new,controls=controls,
        groups=groups,minimum_list_interval_seconds=10,
        map_association_policy='quarantine_known_asset_map_mismatch_continue',
        known_asset_map_ids=sorted(known_asset_maps if known_asset_maps is not None else {m for t in expanded['targets'] for m in t['expected_maps']}),
        maximum_list_queries=1+len(groups)+len(controls)+len(new),
        strategy='One three-area control query; groups of at most 8. At most one single-target fallback per missing/quarantined target, including controls. No reconnect; reject/unknown packet/area mismatch stops.',
        candidate_snapshot_not_server_complete=True,full_world_coverage=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('previous','expanded','output'):p.add_argument('--'+flag,required=True)
    p.add_argument('--assets',help='Optional local asset inventory to recognize and quarantine known map variants')
    a=p.parse_args();load=lambda p:json.loads(Path(p).read_text())
    known=None
    if a.assets:
        known={int.from_bytes(bytes(map(int,Path(m['path']).name[:12][1:].split('_'))),'big') for m in load(a.assets)['maps']}
    result=build(load(a.previous),load(a.expanded),known)
    result['input_sha256']={path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in [a.previous,a.expanded]}
    if a.assets:result['input_sha256'][a.assets]=hashlib.sha256(Path(a.assets).read_bytes()).hexdigest()
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ['status','new_target_count','maximum_list_queries','server_group_queries_tested']}))


if __name__=='__main__':main()
