"""Offline gap triage. No game access, tickets, HTTP or server requests.

World distances are geometric estimates across canonical 256m tiles in the
same world. They do not establish walkability, runtime map or native visibility.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path


def map_name(value):
    return 'm' + '_'.join(f'{n:02d}' for n in value.to_bytes(4, 'big'))


def point(map_id, position):
    major, x, z, variant = map_id.to_bytes(4, 'big')
    if variant:
        raise ValueError('Unverified variants cannot enter spatial estimates')
    if len(position) != 3 or any(not math.isfinite(n) for n in position):
        raise ValueError('Finite XYZ required')
    if major in (60, 61):
        return major, (position[0] + 256*x, position[1], position[2] + 256*z)
    return map_id, tuple(position)


def nearest(map_id, position, records):
    domain, xyz = point(map_id, position)
    best = None
    for record in records:
        other_domain, other = point(record['map'], record['position'])
        if domain != other_domain:
            continue
        d2 = sum((a-b)**2 for a, b in zip(xyz, other))
        key = (d2, record['id'])
        if best is None or key < best[0]:
            best = (key, record)
    if best is None:
        return None
    key, record = best
    return dict(record_id=record['id'], map=map_name(record['map']),
                distance_metres=round(math.sqrt(key[0]), 3),
                same_default_map=record['map'] == map_id,
                runtime_visibility_verified=False)


def audit(pack, params, coverage, manifest, checkpoints):
    records = pack['messages']
    counts = collections.Counter(r['map'] for r in records)
    routes = collections.defaultdict(list)
    for checkpoint in checkpoints:
        for stage in checkpoint['stages']:
            for pair in stage['requested_pairs']:
                pair_key = ':'.join(map(str, pair))
                routes[tuple(pair)].append(dict(
                    query=stage['query'], requested_pairs=stage['requested_pairs'],
                    returned_entries=stage['returned_entries'],
                    accepted_for_pair=stage.get('accepted_pair_counts', {}).get(pair_key, 0),
                    response_at_or_above_64=stage['returned_entries'] >= 64))
    grace_rows = []
    for row in params['parameters']['BonfireWarpParam']['rows']:
        f = row['fields']
        map_id = int.from_bytes(bytes([f['areaNo'], f['gridXNo'], f['gridZNo'], 0]), 'big')
        pos = [f['posX'], f['posY'], f['posZ']]
        grace_rows.append(dict(parameter_id=row['id'], text_id=f['textId1'],
            default_map=map_name(map_id), default_map_sample_count=counts[map_id],
            nearest=nearest(map_id, pos, records),
            runtime_default_map_correspondence_verified=False))
    missing = [r for r in coverage['regions'] if not r['received_samples']]
    direct = [r for r in missing if r['asset_map_references']]
    no_reference = [r for r in missing if not r['asset_map_references']]
    candidates = []
    missing_regions = {r['region_id'] for r in direct}
    for target in manifest['targets']:
        no_map_sample = all(not counts[m] for m in target['expected_maps'])
        if not no_map_sample and target['pair'][1] not in missing_regions:
            continue
        candidates.append(dict(**target, selection_reason=(
            'no_samples_in_any_expected_map' if no_map_sample else 'referenced_region_without_samples'),
            previous_responses=routes[tuple(target['pair'])],
            server_requests_authorized=False))
    candidates.sort(key=lambda t: (t['pair'][1] not in missing_regions, t['pair']))
    summary = dict(records=len(records), maps=len(counts),
        enabled_regions_without_samples=len(missing),
        unsampled_regions_with_direct_asset_references=len(direct),
        unsampled_regions_without_direct_asset_references=len(no_reference),
        grace_entries=len(grace_rows),
        grace_entries_without_same_map_samples=sum(not r['default_map_sample_count'] for r in grace_rows),
        grace_entries_with_neighbor_only_sample_within_250m=sum(
            not r['default_map_sample_count'] and r['nearest'] is not None
            and r['nearest']['distance_metres'] <= 250 for r in grace_rows),
        proposed_single_query_targets=len(candidates),
        previous_stages_at_or_above_64=sum(s['returned_entries'] >= 64
            for c in checkpoints for s in c['stages']))
    return dict(schema_version=1, status='OFFLINE_AUDIT_ONLY', summary=summary,
        full_world_coverage=False, server_requests_sent=0,
        unsampled_referenced_regions=direct, unsampled_unresolved_regions=no_reference,
        grace_spatial_estimates=grace_rows, retry_candidates=candidates,
        limitations=[
            'Unreferenced enabled rows are unresolved, not proven unused or unplayable.',
            'Empty past replies do not prove absence; retry success is unknown.',
            'No prior 64-entry saturation does not establish absence of a lower server cap.',
            'Cross-tile distances are geometric only. Indoor coordinates are never compared across maps.',
            'Default warp maps and native loaded maps may differ; no new gameplay proof.',
            'Existing replay selector searches the exact loaded map. Neighbor-only estimates do not prove visibility.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('pack', 'params', 'coverage', 'manifest', 'output'):
        p.add_argument('--'+flag, required=True)
    p.add_argument('--checkpoint', action='append', required=True)
    a = p.parse_args()
    load = lambda n: json.loads(Path(n).read_text(encoding='utf-8'))
    result = audit(load(a.pack), load(a.params), load(a.coverage),
                   load(a.manifest), [load(n) for n in a.checkpoint])
    inputs = [a.pack, a.params, a.coverage, a.manifest] + a.checkpoint
    result['input_sha256'] = {n: hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in inputs}
    with Path(a.output).open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
