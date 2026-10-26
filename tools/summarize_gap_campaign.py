"""Offline accounting for the approved v10 gap recheck. Never makes requests."""
import collections
import hashlib
import json
from pathlib import Path
from capture_client_cache import semantics, fingerprint
from merge_official_packs import merge
from review_campaign_protocol import review

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = dict(base=ROOT/'data/official-expansion-23385.json',
        checkpoint=ROOT/'build/capture/protocol-gap-candidates-v10.json',
        quarantine=ROOT/'build/capture/protocol-gap-candidates-v10-quarantine.json',
        receipt=ROOT/'evidence/protocol-gap-result-v10.json',
        plan=ROOT/'build/research/gap-recheck-plan-v10.json',
        approval=ROOT/'evidence/gap-recheck-authorization-v10.json',
        proof=ROOT/'evidence/protocol-cohort-reviewed-result-v3.json',
        ledger=ROOT/'build/research/protocol-private/authorized-pilot-ledger.json')
    data = {k: json.loads(p.read_text(encoding='utf-8')) for k, p in paths.items()}
    digest = hashlib.sha256(paths['plan'].read_bytes()).hexdigest()
    if (data['approval'].get('approved_by_user') is not True
            or data['approval']['plan_sha256'] != digest or data['receipt']['plan_sha256'] != digest):
        raise ValueError('Exact approval and receipt required')
    cohort, reviewed = review(*(data[k] for k in ('checkpoint','quarantine','receipt','plan','proof')))
    ledger = data['ledger']
    events = [e for e in ledger['events'] if e.get('campaign_sha256') == digest]
    sessions = [e for e in events if e['kind'] == 'session']
    lists = [e for e in events if e['kind'] == 'message_list']
    if (len(sessions) != 1 or len(lists) != data['receipt']['message_list_requests']
            or ledger['session_attempts'] != 10 or ledger['message_list_attempts'] != 933+len(lists)
            or ledger.get('campaign_segment_active') is not False
            or len(lists) > 126):
        raise ValueError('Reserved request ledger differs from receipt or is still active')
    intervals = [b['utc_unix_seconds']-a['utc_unix_seconds'] for a, b in zip(lists, lists[1:])]
    if any(t < 10 for t in intervals):
        raise ValueError('Minimum request interval violated')
    before = {fingerprint(semantics(r)): r for r in data['base']['messages']}
    after = merge([data['base'], cohort])['messages']
    original_maps = {r['map'] for r in data['base']['messages']}
    target_stages = [s for s in data['receipt']['stages'] if s['query'].startswith('gap-single-')]
    control_stages = [s for s in data['receipt']['stages'] if s['query'].startswith('known-control-')]
    novel = [r for r in cohort['messages'] if fingerprint(semantics(r)) not in before]
    ratings = [r for r in cohort['messages'] if fingerprint(semantics(r)) in before and
               (r['good'], r['poor']) != (before[fingerprint(semantics(r))]['good'], before[fingerprint(semantics(r))]['poor'])]
    result = dict(status='FINISHED_OFFLINE_REVIEW',
        queries_completed=reviewed['queries_completed'], stopped_early=reviewed['stopped_early'],
        targets_queried=len(target_stages), targets_with_accepted_records=sum(s['accepted_entries']>0 for s in target_stages),
        target_accepted_records=sum(s['accepted_entries'] for s in target_stages),
        control_accepted_records=sum(s['accepted_entries'] for s in control_stages),
        quarantine_records=reviewed['quarantined_records'],
        cohort_distinct_records=len(cohort['messages']), novel_semantic_records=len(novel),
        changed_appraisal_snapshots=len(ratings), merged_records=len(after),
        original_map_count=len(original_maps), merged_map_count=len({r['map'] for r in after}),
        added_map_ids=sorted({r['map'] for r in after}-original_maps),
        cumulative_authentications=ledger['session_attempts'], cumulative_lists=ledger['message_list_attempts'],
        minimum_reserved_request_interval_seconds=round(min(intervals),6) if intervals else None,
        full_world_coverage=False, new_pack_gameplay_verified=False,
        stable_release_modified=False, runtime_dll_modified=False,
        note='Controls and gap targets are counted separately. New semantics or appraisals in old maps are not new map coverage. No new game test implied.',
        input_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()})
    # The private ledger path is evidence provenance only; its contents/identities are not exported.
    out = ROOT/'evidence/gap-recheck-outcome-v10.json'
    with out.open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'input_sha256'}))


if __name__ == '__main__': main()
