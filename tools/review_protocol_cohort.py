"""Promote one bounded authenticated cohort after an exact offline UI witness.

Other rows share protocol provenance, not individual UI verification. This is
distinct from normal official-client acquisition; never relabel the source.
"""
import argparse
import hashlib
import json
from pathlib import Path
from capture_client_cache import semantics, fingerprint
from merge_official_packs import merge


def review(candidates, receipt, native, display, evidence):
    if (candidates.get('type') != 'unverified_independent_protocol_candidates'
            or candidates.get('finished') is not True
            or receipt.get('session_rpc_success') is not True
            or receipt.get('checkpoint_saved') is not True
            or receipt.get('error') or evidence.get('reviewed') is not True):
        raise ValueError('Completed authenticated receipt and explicit review required')
    for stage in receipt['stages']:
        if isinstance(stage, dict) and (stage['unexpected_map_counts'] or stage['unexpected_pair_counts']):
            raise ValueError('Wrong target response')
    for value in (native, display):
        guard = value['offline']
        if guard['online'] or guard['menu_online_enabled'] or guard['menu_property_initialized'] >= -1:
            raise ValueError('Strict offline witness required')
    selected = [i['message'] for m in display['managers'] for i in m['instances']
                if i['selected'] and i['constructed_local'] and 'message' in i]
    if len(selected) != 1:
        raise ValueError('Unique selected Mod display required')
    shown = selected[0]
    rows = [semantics(r) for r in candidates['records']]
    matches = [r for r in rows if all(r[k] == v for k, v in evidence['witness_fields'].items())]
    if len(matches) != 1:
        raise ValueError('Unique semantic witness required')
    witness = matches[0]
    for key in ('map','area','template1','word1','conjunction','template2','word2','good','poor'):
        if shown[key] != witness[key]:
            raise ValueError('Selected display field mismatch')
    if shown['block_position'] != witness['position']:
        raise ValueError('Original position mismatch')
    if not any(r['constructed_local'] and semantics(r) == witness for r in native['items']):
        raise ValueError('Full native witness mismatch')
    if witness['good'] + witness['poor'] != evidence['ui_total_appraisals']:
        raise ValueError('UI appraisal mismatch')
    pack = merge([dict(schema_version=1, game='eldenring', source_type='official_protocol_sample',
        messages=[dict(r, id='7d'+fingerprint(r)[:14]) for r in rows])])
    pack['description'] = ('Finite anonymous authenticated official-service response cohort, independent '
        'experimental protocol. One exact original-position offline native reading UI witness; '
        'other rows are not individually UI verified. Not normal-client receipt or full-world coverage.')
    report = dict(source_type=pack['source_type'], records=len(pack['messages']),
        maps=sorted({r['map'] for r in rows}), individually_offline_ui_matched=1,
        individually_online_ui_matched=0, witness_candidate_key=fingerprint(witness),
        original_position_preserved=True, full_world_coverage=False)
    return pack, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('candidates','receipt','native','display','review','output','report'):
        p.add_argument('--'+flag, required=True)
    a = p.parse_args()
    load = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
    evidence = load(a.review)
    for path, digest in evidence['file_sha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise ValueError('Review evidence file changed')
    pack, report = review(load(a.candidates), load(a.receipt), load(a.native), load(a.display), evidence)
    for path, value in [(Path(a.output),pack),(Path(a.report),report)]:
        with path.open('x', encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
            f.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
