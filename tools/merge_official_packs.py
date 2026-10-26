"""Merge already reviewed, anonymous official-client packs in input order.

Does not promote raw cache candidates or construct records. Later observations
replace appraisal values for identical semantics. No game or network access.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

FIELDS = {'map', 'area', 'secondary_area', 'position', 'yaw', 'template1',
          'word1', 'conjunction', 'template2', 'word2', 'good', 'poor', 'id'}


def merge(packs):
    records = {};sources=set()
    for pack in packs:
        if pack.get('schema_version') != 1 or pack.get('game') != 'eldenring' or pack.get('source_type') not in ('official_client_sample','official_protocol_sample','official_sample'):
            raise ValueError('Expected reviewed official-client runtime pack, not candidates/constructed data')
        sources.add(pack['source_type'])
        for r in pack['messages']:
            if set(r) != FIELDS:
                raise ValueError('Anonymous semantic allowlist mismatch')
            if not isinstance(r['id'], str) or len(r['id']) != 16 or not r['id'].startswith('7d'):
                raise ValueError('Official local ID namespace')
            int(r['id'], 16)
            for k in FIELDS - {'position', 'yaw', 'id'}:
                maximum = 0xfffffffe if k == 'map' else (0xffffffff if k in ('area', 'secondary_area') else (9999 if k in ('good', 'poor') else 65535))
                if type(r[k]) is not int or not 0 <= r[k] <= maximum:
                    raise ValueError('Integer field out of range')
            if not r['map'] or not r['area'] or not r['template1']:
                raise ValueError('Required native semantic field')
            if not r['template2'] and (r['word2'] or r['conjunction']):
                raise ValueError('Incomplete second phrase')
            if not isinstance(r['position'], list) or len(r['position']) != 3:
                raise ValueError('Position vector')
            if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e6 for v in r['position']+[r['yaw']]):
                raise ValueError('Coordinate out of bounds')
            semantic = {k: v for k, v in r.items() if k not in ('id', 'good', 'poor')}
            digest = hashlib.sha256(json.dumps(semantic, sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            records[digest] = dict(r, id='7d'+digest[:14])
    output = [records[k] for k in sorted(records)]
    if len({r['id'] for r in output}) != len(output):
        raise ValueError('Truncated semantic hash collision')
    source=next(iter(sources)) if len(sources)==1 else 'official_sample'
    return dict(schema_version=1, game='eldenring', source_type=source,
        description='Merged finite reviewed official snapshots; client/protocol cohort provenance recorded separately; later input wins for appraisal snapshots. '
                    'No constructed records, identity fields or full-world coverage claim.', messages=output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pack', action='append', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    result = merge([json.loads(Path(x).read_text(encoding='utf-8')) for x in a.pack])
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(records=len(result['messages']),
        maps=len({r['map'] for r in result['messages']}))))


if __name__ == '__main__':
    main()
