"""Build a finite, evidence-linked collection inventory. No network/process access.

Direct collision references are candidates, not server-validated coverage. LOD,
variant maps and unlinked outdoor regions remain explicit gaps, never guessed.
"""
import argparse
import hashlib
import json
from pathlib import Path
from native_region_pair import native_pair

ROOT = Path(__file__).resolve().parents[1]


def build(maps, enabled, samples):
    targets = {}
    canonical = set()
    for entry in maps:
        name = Path(entry['path']).name.removesuffix('.msb.dcx')
        parts = list(map(int, name[1:].split('_')))
        if parts[3] != 0:
            continue
        canonical.add(name)
        map_id = int.from_bytes(bytes(parts), 'big')
        area_regions={r['play_region_id'] for r in entry.get('play_area_regions',[])}
        for region in sorted(enabled.intersection(set(entry['collision_play_regions']) | area_regions)):
            pair = native_pair(region, map_id)
            target = targets.setdefault(pair, dict(pair=list(pair), expected_maps=[], bases=[]))
            if map_id not in target['expected_maps']:
                target['expected_maps'].append(map_id)
            for kind, values in [('local_collision_reference',set(entry['collision_play_regions'])),
                                 ('local_playarea_reference',area_regions)]:
                if region in values:
                    target['bases'].append(dict(kind=kind, map=name,
                        msb_sha256=entry['msb_sha256'], server_verified=False))
    for sample in samples:
        pair = native_pair(sample['area'], sample['map'])
        target = targets.setdefault(pair, dict(pair=list(pair), expected_maps=[], bases=[]))
        if sample['map'] not in target['expected_maps']:
            target['expected_maps'].append(sample['map'])
        # A normal-client received record proves semantic provenance, not that
        # our derived independent query pair has itself been accepted.
        basis = dict(kind='received_semantic_sample', map=sample['map'], server_verified=False)
        if basis not in target['bases']:
            target['bases'].append(basis)
    covered = {b['map'] for t in targets.values() for b in t['bases'] if isinstance(b['map'], str)}
    ordered = []
    for pair, target in sorted(targets.items()):
        target['expected_maps'].sort()
        target['id'] = 'area-' + str(pair[0]) + '-' + str(pair[1])
        ordered.append(target)
    return dict(schema_version=1, status='PREPARED_NOT_AUTHORIZED',
        full_world_coverage=False, queries_sent_by_this_tool=0,
        query_mode='one_pair_per_request', minimum_interval_seconds=10,
        targets=ordered, target_count=len(ordered),
        estimated_minimum_query_minutes=round(max(0, len(ordered)-1)*10/60, 2),
        enabled_rows_without_target=sorted(enabled - {p[1] for p in targets}),
        canonical_maps_without_direct_collision_target=sorted(canonical-covered),
        warning='A local reference is a query candidate, not a verified response. Empty replies do not prove absence. Map assets include unused content; no completeness claim.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--maps', default=str(ROOT/'build/research/all-map-grace-candidates.json'))
    a = p.parse_args()
    map_path = Path(a.maps).resolve()
    param_path = ROOT/'build/research/grace-region-params.json'
    sources = [ROOT/'data/official-expansion-327.json', ROOT/'build/capture/protocol-routed-candidates-v3.json']
    maps = json.loads(map_path.read_text())['maps']
    rows = json.loads(param_path.read_text())['parameters']['PlayRegionParam']['rows']
    samples = []
    for path in sources:
        data = json.loads(path.read_text())
        samples.extend(data.get('messages', data.get('records', [])))
    result = build(maps, {r['id'] for r in rows if r['fields']['enableBloodMessage']}, samples)
    receipt_path = ROOT/'evidence/protocol-routed-result-v3.json'
    receipt = json.loads(receipt_path.read_text())
    verified = {tuple(s['requested_pair']) for s in receipt['stages'] if isinstance(s,dict)
                and not s['unexpected_map_counts'] and not s['unexpected_pair_counts']}
    for target in result['targets']:
        target['independent_pair_previously_verified'] = tuple(target['pair']) in verified
    result['input_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in [map_path, param_path, *sources, receipt_path]}
    output = Path(a.output).resolve()
    if not output.is_relative_to(ROOT/'build/research') or output.exists():
        raise ValueError('New workspace research output required')
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['status','target_count','estimated_minimum_query_minutes','full_world_coverage']}))


if __name__ == '__main__':
    main()
