"""Offline-only cache comparison, after normal unmodified online gameplay.

Candidates are NOT official samples until their receipt and UI are corroborated.
No online process access, injection, requests, raw message keys or identity export.
"""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path

FIELDS = ('map', 'area', 'secondary_area', 'position', 'yaw', 'template1',
          'word1', 'conjunction', 'template2', 'word2', 'good', 'poor')


def semantics(item):
    value = {key: item[key] for key in FIELDS}
    if not isinstance(value['position'], list) or len(value['position']) != 3:
        raise ValueError('Invalid vector')
    if any(not math.isfinite(v) or abs(v) > 1e6
           for v in value['position'] + [value['yaw']]):
        raise ValueError('Invalid coordinate')
    return value


def fingerprint(value):
    # Exclude ratings from comparison: a rating change alone is not a new receipt.
    immutable = {k: v for k, v in value.items() if k not in ('good', 'poor')}
    return hashlib.sha256(json.dumps(immutable, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def anonymous_records(snapshot):
    records = {}
    for item in snapshot['items']:
        if item['constructed_local']:
            continue
        value = semantics(item)
        records[fingerprint(value)] = value
    return records


def compare(before, after):
    old = anonymous_records(before)
    new = anonymous_records(after)
    return [dict(candidate_key=key, **value) for key, value in new.items()
            if key not in old]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--baseline', help='Prior exclusion snapshot from this tool')
    p.add_argument('--import-baseline', help='Existing offline observation, baseline only')
    a = p.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = Path(a.output).resolve()
    if not output.is_relative_to(root / 'build' / 'capture') or output.exists():
        raise ValueError('Use a new output under build/capture; candidates are private')
    if a.import_baseline and a.baseline:
        raise ValueError('Import is only for creating the exclusion baseline')
    if a.import_baseline:
        snapshot = json.loads(Path(a.import_baseline).read_text(encoding='utf-8'))
        guard = snapshot['offline']
        if guard['online'] != 0 or guard['menu_online_enabled'] != 0:
            raise ValueError('Imported observation was not offline')
    else:
        from observe import Reader
        reader = Reader()  # Refuses EAC, online state or another game image.
        try:
            if any(name.lower().startswith('erofflinemessages')
                   for name, *_ in reader.modules):
                raise RuntimeError('Replay DLL present; use empty offline baseline profile')
            snapshot = reader.snapshot()
            if int(snapshot['map'], 16) == 0xffffffff:
                raise RuntimeError('Continue a character offline before reading its cache')
        finally:
            reader.close()
    records = anonymous_records(snapshot)
    result = dict(schema_version=1, timestamp=datetime.datetime.now().astimezone().isoformat(),
        type='offline_cache_exclusion_baseline', official_samples=0,
        game_sha256=snapshot['sha256'], records=list(records.values()))
    if a.baseline:
        baseline = json.loads(Path(a.baseline).read_text(encoding='utf-8'))
        if (baseline['type'] != 'offline_cache_exclusion_baseline'
                or baseline['game_sha256'] != snapshot['sha256']):
            raise ValueError('Baseline provenance mismatch')
        old = {fingerprint(v) for v in baseline['records']}
        candidates = [dict(candidate_key=k, **v) for k, v in records.items() if k not in old]
        result.update(type='unverified_client_cache_candidates', records=candidates,
            baseline_records=len(old), observed_nonconstructed_records=len(records),
            warning='Set difference alone is not proof of official player origin. '
                    'Validate normal online receipt, native text, map, coordinates and appraisals '
                    'before promoting any record. Not a runtime pack.')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
                      + '\n', encoding='utf-8')
    print(json.dumps(dict(type=result['type'], records=len(result['records']),
                         official_samples=0, output=str(output)), ensure_ascii=False))


if __name__ == '__main__':
    main()
