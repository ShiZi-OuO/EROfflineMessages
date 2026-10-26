"""Static grace-map association, not teleport/gameplay/whole-map acceptance."""
import argparse
import collections
import json
from pathlib import Path


def audit(params,records):
    rows=params['parameters']['BonfireWarpParam']['rows'];counts=collections.Counter(r['map'] for r in records)
    associations=[]
    for row in rows:
        f=row['fields'];parts=[f['areaNo'],f['gridXNo'],f['gridZNo'],0]
        if any(not isinstance(n,int) or not 0<=n<=255 for n in parts):raise ValueError('Invalid parameter map component')
        map_id=int.from_bytes(bytes(parts),'big')
        associations.append(dict(parameter_id=row['id'],map='m'+'_'.join(f'{n:02d}' for n in parts),
            map_id=map_id,samples_in_same_map=counts[map_id],
            near_grace_reading_verified=False,default_map_index_requires_runtime_correspondence=True))
    maps={r['map_id'] for r in associations}
    return dict(parameter_entries=len(rows),parameter_map_ids=len(maps),
        parameter_map_ids_with_samples=sum(bool(counts[m]) for m in maps),
        entries_in_maps_with_samples=sum(bool(r['samples_in_same_map']) for r in associations),
        maps_without_samples=sorted({r['map'] for r in associations if not r['samples_in_same_map']}),
        full_world_coverage=False,actual_teleport_test=False,
        warning='Parameter map components with default index zero are a static association. Same-map samples do not establish samples near every grace or complete playable-world coverage.',
        associations=associations)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--params',required=True)
    p.add_argument('--pack',required=True);p.add_argument('--candidates');p.add_argument('--output',required=True)
    a=p.parse_args();load=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    rows=load(a.pack)['messages']
    if a.candidates:rows+=load(a.candidates)['records']
    report=audit(load(a.params),rows)
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('associations','warning')}))
