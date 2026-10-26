"""Audit grouped response checkpoints without promoting quarantined records."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
from capture_client_cache import FIELDS,semantics,fingerprint
from merge_official_packs import merge
from native_region_pair import native_pair


def review(checkpoint,receipt,plan,parser_proof):
    if (not checkpoint.get('finished') or not receipt.get('session_rpc_success')
            or not receipt.get('checkpoint_saved') or checkpoint['stages']!=receipt['stages']
            or parser_proof.get('individually_offline_ui_matched',0)<1):
        raise ValueError('Finished authenticated checkpoint and prior parser witness required')
    targets={t['id']:t for t in plan['controls']+plan['targets']}
    groups={g['id']:g['target_ids'] for g in plan['groups']}
    groups['known-control-three']=[t['id'] for t in plan['controls']]
    fallback=set();eligible_fallback=set();seen_groups=set();admitted=[];cursor=0;quarantined=0
    requested=set();with_samples=set();queries=[s for s in receipt['stages'] if isinstance(s,dict)]
    for index,stage in enumerate(queries):
        ids=stage['target_ids']
        if stage['fallback']:
            if len(ids)!=1 or ids[0] in fallback or ids[0] not in requested or ids[0] not in eligible_fallback:
                raise ValueError('Invalid/repeated single-target fallback')
            fallback.add(ids[0])
        else:
            if stage['query'] not in groups or ids!=groups[stage['query']] or stage['query'] in seen_groups:
                raise ValueError('Group differs from immutable plan')
            seen_groups.add(stage['query'])
        requested.update(ids)
        routing={tuple(targets[i]['pair']):set(targets[i]['expected_maps']) for i in ids}
        if [list(p) for p in routing]!=stage['requested_pairs']:
            raise ValueError('Requested pairs differ from planned targets')
        if stage.get('disposition')=='quarantined_map_association':
            if stage['unexpected_pair_counts'] or not stage['unexpected_map_counts']:
                raise ValueError('Invalid map quarantine declaration')
            if not set(map(int,stage['unexpected_map_counts'])).issubset(set(plan['known_asset_map_ids'])):
                raise ValueError('Unknown map cannot be continued as known-map quarantine')
            if not stage['fallback']:eligible_fallback.update(ids)
            quarantined+=stage['returned_entries'];continue
        if stage['unexpected_pair_counts'] or stage['unexpected_map_counts']:
            if index!=len(queries)-1 or not receipt.get('error'):
                raise ValueError('Unquarantined mismatch must stop')
            continue
        if stage.get('disposition')!='accepted':raise ValueError('Unknown response disposition')
        rows=checkpoint['records'][cursor:cursor+stage['returned_entries']]
        if len(rows)!=stage['returned_entries']:raise ValueError('Incomplete grouped checkpoint')
        counts=collections.Counter()
        for row in rows:
            if set(row)!=set(FIELDS)|{'candidate_key'}:raise ValueError('Anonymous allowlist mismatch')
            value=semantics(row);pair=native_pair(value['area'],value['map'])
            if pair not in routing or value['map'] not in routing[pair] or fingerprint(value)!=row['candidate_key']:
                raise ValueError('Row does not match its own query pair/map')
            counts[f'{pair[0]}:{pair[1]}']+=1
            with_samples.update(i for i in ids if targets[i]['pair']==list(pair))
            admitted.append(dict(value,id='7d'+fingerprint(value)[:14]))
        if dict(counts)!=stage['entries_per_pair']:raise ValueError('Per-pair record counts differ')
        if not stage['fallback']:
            eligible_fallback.update(i for i in ids if not counts.get(':'.join(map(str,targets[i]['pair'])),0))
        cursor+=len(rows)
    if cursor!=len(checkpoint['records']) or cursor!=receipt['anonymous_candidate_records']:
        raise ValueError('Unattributed grouped records')
    if quarantined!=receipt['quarantined_candidate_records']:raise ValueError('Quarantine count mismatch')
    pack=merge([dict(schema_version=1,game='eldenring',source_type='official_protocol_sample',messages=admitted)])
    pack['description']=('Finite anonymous authenticated grouped official-service response cohort. '
        'Only per-pair/map validated accepted responses; quarantine excluded. Prior protocol parser '
        'reading witness is not individual UI verification of these records. No full-server/world claim.')
    new_ids={t['id'] for t in plan['targets']}
    report=dict(source_type=pack['source_type'],records=len(pack['messages']),received_record_count=cursor,
        queries_completed=len(queries),fallback_queries=len(fallback),quarantined_records=quarantined,
        new_targets_requested=len(requested&new_ids),new_targets_with_finite_samples=len(with_samples&new_ids),
        new_targets_without_finite_samples=sorted(new_ids-with_samples),
        stopped_early=bool(receipt.get('error') or receipt.get('bounded_stop_reason')) or not new_ids.issubset(requested),
        individually_offline_ui_matched=0,full_world_coverage=False,gameplay_acceptance=False)
    return pack,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('checkpoint','receipt','plan','authorization','parser-proof','output','report'):p.add_argument('--'+flag,required=True)
    a=p.parse_args();load=lambda p:json.loads(Path(p).read_text())
    auth=load(a.authorization)
    if not auth.get('approved_by_user') or auth['plan_sha256']!=hashlib.sha256(Path(a.plan).read_bytes()).hexdigest():
        raise ValueError('Exact explicitly authorized group plan required')
    pack,report=review(load(a.checkpoint),load(a.receipt),load(a.plan),load(a.parser_proof))
    report['input_sha256']={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest()
        for p in [a.checkpoint,a.receipt,a.plan,a.authorization,a.parser_proof]}
    for path,value in [(Path(a.output),pack),(Path(a.report),report)]:
        with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('input_sha256','new_targets_without_finite_samples')}))


if __name__=='__main__':main()
