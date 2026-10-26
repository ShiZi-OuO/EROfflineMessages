"""Read local research metadata and anonymous packs; never connects to a game/server.

The inventory is a collection checklist, not a claim that every parameter row is
a separate playable map or that one sample covers an entire region.
"""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path


def map_name(value):
    return 'm' + '_'.join(f'{b:02d}' for b in value.to_bytes(4, 'big'))


def inventory(params, maps, packs):
    enabled = {r['id'] for r in params['parameters']['PlayRegionParam']['rows']
               if r['fields']['enableBloodMessage'] == 1}
    links = collections.defaultdict(set)
    archives = collections.defaultdict(set)
    for m in maps['maps']:
        name = re.search(r'm\d{2}_\d{2}_\d{2}_\d{2}', m['path'])
        if not name:
            raise ValueError('Invalid map name')
        references=set(m['collision_play_regions']) | {r['play_region_id'] for r in m.get('play_area_regions',[])}
        for region in references:
            links[region].add(name.group())
            archives[region].add(m['archive'])
    seen = set()
    counts = collections.Counter()
    map_counts = collections.Counter()
    for pack in packs:
        if pack['game'] != 'eldenring' or pack['source_type'] not in ('official_client_sample','official_protocol_sample','official_sample'):
            raise ValueError('Only separately reviewed official source packs admitted')
        for record in pack['messages']:
            # Deduplicate by semantics, excluding mutable appraisal snapshots and IDs.
            semantic = {k: v for k, v in record.items() if k not in ('id', 'good', 'poor')}
            key = hashlib.sha256(json.dumps(semantic, sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            counts[record['area']] += 1
            map_counts[map_name(record['map'])] += 1
    rows = [dict(region_id=region, asset_map_references=sorted(links[region]),
                 archives=sorted(archives[region]), received_samples=counts[region],
                 status='has_finite_samples' if counts[region] else 'not_collected',
                 whole_region_coverage_verified=False)
            for region in sorted(enabled)]
    return dict(schema_version=1, source='local parameter/map metadata and verified finite packs',
                target='base game and installed DLC playable message regions',
                enabled_parameter_rows=len(enabled),
                parameter_rows_with_samples=sum(bool(counts[r]) for r in enabled),
                unique_received_samples=len(seen), sample_maps=dict(sorted(map_counts.items())),
                sampled_areas_outside_enabled_inventory=sorted(set(counts)-enabled),
                full_world_coverage=False,
                warning='Parameter rows, map assets and server query areas are different units. '
                        'Asset references can be parent/LOD/variant maps. Sample presence is not whole-region coverage.',
                regions=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--params', required=True)
    p.add_argument('--maps', required=True)
    p.add_argument('--pack', action='append', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    read = lambda name: json.loads(Path(name).read_text(encoding='utf-8'))
    result = inventory(read(a.params), read(a.maps), [read(x) for x in a.pack])
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'regions'}, indent=2))


if __name__ == '__main__':
    main()
