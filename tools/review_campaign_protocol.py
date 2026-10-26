"""Audit per-row quarantine and repeated controls across bounded segments."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
from capture_client_cache import FIELDS,semantics,fingerprint
from merge_official_packs import merge
from native_region_pair import native_pair


def review(checkpoint,quarantine,receipt,plan,parser_proof):
    if (not receipt.get('session_rpc_success') or not receipt.get('checkpoint_saved')
            or not receipt.get('quarantine_checkpoint_saved')
            or not checkpoint.get('finished') or not quarantine.get('finished')
            or checkpoint['stages']!=receipt['stages'] or quarantine['stages']!=receipt['stages']
            or parser_proof.get('individually_offline_ui_matched',0)<1):
        raise ValueError('Finished checkpoints and original parser UI witness required')
    targets={t['id']:t for t in plan['controls']+plan['targets']}
    groups=plan['groups'];controls=[t['id'] for t in plan['controls']]
    cursor=0;qcursor=0;group_cursor=0;admitted=[];requested=set();with_samples=set();eligible=set();used=set()
    session=0;control_cursor=0;session_queries=collections.Counter()
    for stage in receipt['stages']:
        if not isinstance(stage,dict):raise ValueError('Unexpected stage type')
        index=stage['session_index']
        if index!=session:
            if index!=session+1 or index>plan.get('maximum_sessions',2):raise ValueError('Invalid session transition')
            if session:
                previous=receipt['segments'][session-1]
                if not previous.get('normal_close_reason'):raise ValueError('Transition after failure')
            session=index;control_cursor=0
        ids=stage['target_ids'];label=stage['query'];session_queries[index]+=1
        if control_cursor<len(controls):
            wanted=controls[control_cursor]
            if ids!=[wanted] or label!='known-control-'+wanted or stage['fallback']:
                raise ValueError('Session controls missing or reordered')
            control_cursor+=1
        elif stage['fallback']:
            if plan.get('fallback_enabled') is False:raise ValueError('Fallback forbidden by this plan')
            if group_cursor!=len(groups) or len(ids)!=1 or ids[0] not in eligible or ids[0] in used:
                raise ValueError('Invalid/premature/repeated fallback')
            used.add(ids[0])
        else:
            if group_cursor>=len(groups) or label!=groups[group_cursor]['id'] or ids!=groups[group_cursor]['target_ids']:
                raise ValueError('Groups differ from immutable order')
            group_cursor+=1;requested.update(ids)
        routing={tuple(targets[i]['pair']):set(targets[i]['expected_maps']) for i in ids}
        if stage['requested_pairs']!=[list(p) for p in routing] or stage['unexpected_pair_counts']:
            raise ValueError('Unrequested region pair')
        n=stage['accepted_entries'];q=stage['quarantined_entries']
        if n+q!=stage['returned_entries'] or stage['disposition']!=('accepted_with_quarantine' if q else 'accepted'):
            raise ValueError('Partition count/disposition mismatch')
        rows=checkpoint['records'][cursor:cursor+n];held=quarantine['records'][qcursor:qcursor+q]
        if len(rows)!=n or len(held)!=q:raise ValueError('Missing partition records')
        routes=stage['row_routes'];ar=stage['accepted_row_routes']
        if len(routes)!=n+q or len(ar)!=n:raise ValueError('Missing row routes')
        ai=0;qi=0;counts=collections.Counter();raw_counts=collections.Counter();bad_maps=collections.Counter()
        for route in routes:
            pair=tuple(route['pair'])
            if pair not in routing:raise ValueError('Foreign row route')
            is_accepted=ai<n and ar[ai]==route
            row=rows[ai] if is_accepted else held[qi] if qi<q else None
            if row is None or set(row)!=set(FIELDS)|{'candidate_key'}:raise ValueError('Anonymous row allowlist mismatch')
            value=semantics(row)
            if fingerprint(value)!=route['candidate_key'] or row['candidate_key']!=route['candidate_key']:
                raise ValueError('Row/route identity mismatch')
            if value['area']!=pair[1]:raise ValueError('Payload area mismatch')
            raw_counts[':'.join(map(str,pair))]+=1
            if is_accepted:
                if value['map'] not in routing[pair] or native_pair(value['area'],value['map'])!=pair:
                    raise ValueError('Unverified map admitted')
                counts[':'.join(map(str,pair))]+=1;ai+=1
                with_samples.update(i for i in ids if targets[i]['pair']==list(pair))
                admitted.append(dict(value,id='7d'+fingerprint(value)[:14]))
            else:
                if value['map'] in routing[pair]:raise ValueError('Canonical row incorrectly quarantined')
                bad_maps[str(value['map'])]+=1;qi+=1
        if ai!=n or qi!=q or dict(counts)!=stage['accepted_pair_counts'] or dict(raw_counts)!=stage['entries_per_pair'] or dict(bad_maps)!=stage['unexpected_map_counts']:
            raise ValueError('Partition route/count audit failed')
        if not stage['fallback'] and label.startswith('world-group-') and stage['returned_entries']>=64:
            eligible.update(i for i in ids if not counts.get(':'.join(map(str,targets[i]['pair'])),0))
        cursor+=n;qcursor+=q
    if cursor!=len(checkpoint['records']) or cursor!=receipt['anonymous_candidate_records'] or qcursor!=len(quarantine['records']) or qcursor!=receipt['quarantined_candidate_records']:
        raise ValueError('Unattributed records')
    attempts=receipt.get('attempted_queries',[])
    if len(attempts)!=receipt['message_list_requests']:raise ValueError('Missing query attempt ledger')
    if len(attempts)-len(receipt['stages']) not in ((0,1) if receipt.get('error') else (0,)):
        raise ValueError('Only the final failed attempt may lack a response')
    for stage,attempt in zip(receipt['stages'],attempts):
        if any(stage[k]!=attempt[k] for k in ('query','session_index','target_ids','fallback')):
            raise ValueError('Stage/attempt sequence mismatch')
    attempt_counts=collections.Counter(a['session_index'] for a in attempts)
    if (max(attempt_counts.values(),default=0)>plan.get('per_session_query_cap',250)
            or len(attempts)>plan.get('maximum_list_queries',500)):
        raise ValueError('Request cap/count mismatch')
    pack=merge([dict(schema_version=1,game='eldenring',source_type='official_protocol_sample',messages=admitted)])
    pack['description']='Finite anonymous official-service samples; per-row native pair/map validated. Unmapped records excluded. Not full-server or full-world coverage; not individually gameplay verified.'
    new_ids={t['id'] for t in plan['targets']}
    report=dict(records=len(pack['messages']),received_record_count=cursor,quarantined_records=qcursor,
        new_targets_requested=len(requested),new_targets_with_finite_samples=len(with_samples&new_ids),
        new_targets_without_finite_samples=sorted(new_ids-with_samples),queries_completed=sum(session_queries.values()),
        stopped_early=bool(receipt.get('error') or receipt.get('bounded_stop_reason')) or group_cursor!=len(groups),
        individually_offline_ui_matched=0,full_world_coverage=False,gameplay_acceptance=False)
    return pack,report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('checkpoint','quarantine','receipt','plan','authorization','parser-proof','output','report'):p.add_argument('--'+key,required=True)
    a=p.parse_args();load=lambda path:json.loads(Path(path).read_text())
    auth=load(a.authorization)
    if not auth.get('approved_by_user') or auth['plan_sha256']!=hashlib.sha256(Path(a.plan).read_bytes()).hexdigest():
        raise ValueError('Exact approved plan required')
    pack,report=review(*[load(getattr(a,k)) for k in ('checkpoint','quarantine','receipt','plan','parser_proof')])
    report['input_sha256']={str(path):hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in (a.checkpoint,a.quarantine,a.receipt,a.plan,a.authorization,a.parser_proof)}
    for path,value in ((a.output,pack),(a.report,report)):
        with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('input_sha256','new_targets_without_finite_samples')}))
