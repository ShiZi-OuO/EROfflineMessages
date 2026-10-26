"""Build a reviewed cohort pack after normal-client receipt/UI corroboration.

Never promotes candidates on set difference alone. Requires an explicit review
record, a local screenshot hash and an exact unique witness retained by the
offline native cache. Other records share provenance, not individual UI proof.
Unknown nonzero map variants are quarantined without rewriting coordinates.
"""
import argparse
import hashlib
import json
from pathlib import Path
from capture_client_cache import fingerprint, semantics
from merge_official_packs import merge


def review(candidates, native, evidence):
    if candidates.get('type') != 'unverified_saved_cache_candidates':
        raise ValueError('Expected filesystem tour candidates')
    if (candidates.get('game_process_access') is not False
            or candidates.get('save_writes') != 0
            or evidence.get('normal_official_client_receipt_confirmed') is not True
            or evidence.get('reviewed') is not True):
        raise ValueError('Explicit normal-client review required')
    guard = native['offline']
    if guard['online'] or guard['menu_online_enabled'] or guard['menu_property_initialized'] >= -1:
        raise ValueError('Offline comparison gate failed')
    if native['sha256'].lower() != evidence['game_sha256'].lower():
        raise ValueError('Exact image mismatch')
    values = [semantics(r) for r in candidates['records']]
    native_values = {fingerprint(semantics(r)) for r in native['items'] if not r['constructed_local']}
    witness = evidence['witness']
    matches = [r for r in values if all(r[k] == v for k, v in witness['native_fields'].items())]
    if len(matches) != 1 or fingerprint(matches[0]) not in native_values:
        raise ValueError('Unique native-cache witness correspondence required')
    accepted, quarantine = [], []
    for r in values:
        key = fingerprint(r)
        if r['map'] & 255:
            quarantine.append(dict(candidate_key=key, reason='unverified_nonzero_map_variant', **r))
        else:
            accepted.append(dict(r, id='7d' + key[:14]))
    pack = merge([dict(schema_version=1, game='eldenring', source_type='official_client_sample', messages=accepted)])
    pack['description'] = ('Finite anonymous normal official-client tour cohort read from autosaves. '
        'Historical baseline and local replay records excluded. One unique reading UI/native-cache witness; '
        'other records share receipt provenance and are not individually UI verified. '
        'Nonzero map variants quarantined. No full-world coverage claim.')
    report = dict(schema_version=1, candidate_count=len(values), admitted=len(accepted),
        native_cache_semantic_matches=sum(fingerprint(r) in native_values for r in values),
        individually_online_ui_matched=1, quarantined=len(quarantine),
        maps=sorted({r['map'] for r in accepted}), full_world_coverage=False,
        witness_candidate_key=fingerprint(matches[0]),
        native_cache_match_does_not_prove_offline_display=True)
    return pack, quarantine, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('candidates', 'native', 'review', 'output', 'quarantine', 'report'):
        p.add_argument('--'+flag, required=True)
    a = p.parse_args()
    load = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
    evidence = load(a.review)
    shot = Path(evidence['witness']['screenshot'])
    if hashlib.sha256(shot.read_bytes()).hexdigest() != evidence['witness']['screenshot_sha256']:
        raise ValueError('Screenshot evidence changed')
    pack, quarantine, report = review(load(a.candidates), load(a.native), evidence)
    outputs = [(Path(a.output), pack), (Path(a.quarantine), quarantine), (Path(a.report), report)]
    if any(path.exists() for path, _ in outputs):
        raise ValueError('Refusing to overwrite reviewed outputs')
    for path, value in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
