"""Bounded two-segment collection. Requires a new exact-plan approval.

Redirect stdout/stderr to private files: Valve's library may print identities.
Any refusal/protocol/transport failure ends the entire campaign, not a segment.
"""
import argparse
import asyncio
import collections
import datetime
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from campaign_budget import CampaignBudget
from run_grouped_pilot import require_game_closed,CollectionLimitReached
from wire import create_session,message_list
from steam_ticket import SteamTicket
from transport import SessionTransport,HOST
from run_pilot import session_response,message_response
from native_region_pair import native_pair
from rpc_frames import await_response,CandidateCheckpoint
from row_routing import split_rows


def validate_plan(plan):
    controls=plan['controls'];targets=plan['targets']
    all_targets={t['id']:t for t in controls+targets}
    if len(all_targets)!=len(controls)+len(targets):raise ValueError('Duplicate target IDs')
    flat=[i for g in plan['groups'] for i in g['target_ids']]
    if len(flat)!=len(set(flat)) or set(flat)!={t['id'] for t in targets}:
        raise ValueError('Groups must partition all targets')
    if len({g['id'] for g in plan['groups']})!=len(plan['groups']):raise ValueError('Duplicate group IDs')
    if len(controls)!=3 or any(not 1<=len(g['target_ids'])<=2 for g in plan['groups']):
        raise ValueError('Only three known controls and two-target groups supported')
    for t in all_targets.values():
        if not t['expected_maps'] or any(native_pair(t['pair'][1],m)!=tuple(t['pair']) for m in t['expected_maps']):
            raise ValueError('Native pair proof mismatch')
    return all_targets


def partition_response(rows,summary,routing):
    if summary['unexpected_pair_counts']:raise ValueError('Response contains an unrequested region pair')
    accepted,held=split_rows(rows,summary['row_routes'],routing,quarantine_unmapped=True)
    accepted_routes=[r for row,r in zip(rows,summary['row_routes']) if row['map'] in routing[tuple(r['pair'])]]
    counts=collections.Counter(':'.join(map(str,r['pair'])) for r in accepted_routes)
    return accepted,held,dict(accepted_entries=len(accepted),quarantined_entries=len(held),
        accepted_row_routes=accepted_routes,accepted_pair_counts=dict(counts),
        disposition='accepted_with_quarantine' if held else 'accepted')


async def main(a,budget_class=None):
    private=ROOT/'build/research/protocol-private'
    budget=(budget_class or CampaignBudget)(private/'authorized-pilot-ledger.json',a.authorization,a.plan)
    plan=json.loads(Path(a.plan).read_text(encoding='utf-8'));targets=validate_plan(plan)
    output=Path(a.output).resolve();report=Path(a.result).resolve()
    if not output.is_relative_to(ROOT/'build/capture') or output.exists():raise ValueError('New candidate path required')
    if not report.is_relative_to(ROOT/'evidence') or report.exists():raise ValueError('New report path required')
    require_game_closed()
    fields=json.loads((private/'session-known-fields-v2.json').read_text(encoding='utf-8'))
    proof=json.loads((ROOT/'evidence/static-session-version-v2.json').read_text(encoding='utf-8'))
    sha=hashlib.sha256(Path(a.game_exe).read_bytes()).hexdigest()
    if sha!=fields['game_sha256'] or sha!=proof['game_sha256'] or fields['network_version']!=1172:
        raise ValueError('Exact image/version proof mismatch')
    magic=json.loads((private/'session-math-v1.json').read_text(encoding='utf-8'))['first_three_session_fields']
    dns=json.loads(urllib.request.urlopen('https://dns.google/resolve?name='+HOST+'&type=A',timeout=15).read())
    ips=[r['data'] for r in dns.get('Answer',[]) if r['type']==1]
    if not ips:raise RuntimeError('Official endpoint DNS unavailable')
    result=dict(type=plan.get('campaign_kind','two_segment_canonical_collection'),plan_sha256=budget.digest,
        session_rpc_success=False,message_list_requests=0,fallback_requests=0,segments=[],stages=[],
        asynchronous_frames=[],attempted_queries=[],game_memory_access=False,ticket_or_identity_exported=False)
    accepted=[];held=[];deferred=[];fallback_used=set();group_cursor=0;fallback_cursor=0
    saved=CandidateCheckpoint(output,50000)
    quarantined=CandidateCheckpoint(output.with_name(output.stem+'-quarantine.json'),50000)
    try:
        for segment_index in range(1,plan['maximum_sessions']+1):
            require_game_closed()
            segment=dict(session_index=segment_index,message_list_requests=0,authenticated=False)
            result['segments'].append(segment)
            steam=None;transport=None;started=None;normal=False
            try:
                # Spend before any ticket acquisition or server connection. Failures never reconnect.
                budget.reserve('session');started=time.monotonic()
                steam=SteamTicket(a.steam_dll);ticket=steam.acquire()
                transport=SessionTransport(ips[0],a.interface,private);await transport.open()
                completed=set();sequence=1;cap=plan['per_session_seconds']
                request=create_session(1,magic,1172,ticket,platform=fields['field80'],region=fields['field88'],
                    language=fields['field8c'],cross_region=fields['boolean84'],flags=fields['boolean90'],tail=tuple(fields['tail']))
                await transport.send(request);del request,ticket
                raw=await await_response(transport,1,0,result['asynchronous_frames'],completed);completed.add(1)
                metadata=session_response(raw);del raw
                segment.update(authenticated=True,lifetime_metadata=metadata);result['session_rpc_success']=True
                if metadata.get('lifetime_metadata_available'):cap=min(cap,max(0,metadata['remaining_seconds_at_auth']-120))

                async def query(label,items,fallback=False):
                    nonlocal sequence
                    if (result['message_list_requests']>=plan['maximum_list_queries']
                            or segment['message_list_requests']>=plan['per_session_query_cap']):
                        raise CollectionLimitReached('Planned query cap reached')
                    if time.monotonic()-started>=cap-30:raise CollectionLimitReached('Planned duration cap reached')
                    await asyncio.sleep(max(0,10-(time.time()-budget.state['last_list_time'])))
                    require_game_closed()
                    if time.monotonic()-started>=cap-30:raise CollectionLimitReached('Planned duration cap reached after rate wait')
                    if fallback:
                        if len(items)!=1 or items[0]['id'] in fallback_used:raise ValueError('Repeated fallback')
                        fallback_used.add(items[0]['id']);result['fallback_requests']+=1
                    sequence+=1;routing={tuple(t['pair']):set(t['expected_maps']) for t in items}
                    if len(routing)!=len(items):raise ValueError('Duplicate query pairs')
                    budget.reserve('message_list');segment['message_list_requests']+=1;result['message_list_requests']+=1
                    result['attempted_queries'].append(dict(query=label,session_index=segment_index,
                        target_ids=[t['id'] for t in items],fallback=fallback))
                    await transport.send(message_list(sequence,list(routing)))
                    raw=await await_response(transport,sequence,18,result['asynchronous_frames'],completed);completed.add(sequence)
                    rows,summary=message_response(raw,sequence,None,expected_targets=routing,include_routes=True);del raw
                    keep,q,details=partition_response(rows,summary,routing)
                    stage=dict(query=label,session_index=segment_index,target_ids=[t['id'] for t in items],
                        requested_pairs=[list(p) for p in routing],fallback=fallback,**summary,**details)
                    result['stages'].append(stage);accepted.extend(keep);held.extend(q)
                    quarantined.save(held,result['stages']);saved.save(accepted,result['stages'])
                    counts=details['accepted_pair_counts']
                    missing=[t for t in items if not counts.get(':'.join(map(str,t['pair'])),0)]
                    return missing,summary['returned_entries']

                # Single-region controls also respect the two-region request bound.
                for control in plan['controls']:
                    missing,_=await query('known-control-'+control['id'],[control])
                    if missing:raise RuntimeError('Known control empty/quarantined; campaign stopped')
                while group_cursor<len(plan['groups']):
                    group=plan['groups'][group_cursor]
                    missing,count=await query(group['id'],[targets[i] for i in group['target_ids']])
                    if count>=64 and plan.get('fallback_enabled',True):deferred.extend(missing)
                    group_cursor+=1
                while fallback_cursor<len(deferred):
                    t=deferred[fallback_cursor];await query('fallback-'+t['id'],[t],True);fallback_cursor+=1
                result['all_planned_groups_completed']=True;normal=True;segment['normal_close_reason']='Planned work completed'
            except CollectionLimitReached as error:
                normal=True;segment['normal_close_reason']=str(error)
            finally:
                try:
                    if transport is not None:await transport.close()
                except Exception:
                    normal=False;raise RuntimeError('Transport close failed; next segment forbidden')
                finally:
                    if steam is not None:steam.close()
                    segment['elapsed_seconds']=round(time.monotonic()-started,2) if started else 0
                    budget.reserve('segment_normal_close' if normal else 'segment_failed_close')
            if result.get('all_planned_groups_completed'):break
            if segment_index==plan['maximum_sessions'] or result['message_list_requests']>=plan['maximum_list_queries']:
                result['bounded_stop_reason']='Authorized campaign cap reached';break
    except Exception as error:
        result['error_type']=type(error).__name__
        result['error']=str(error) if isinstance(error,(RuntimeError,ValueError,TimeoutError)) else 'Transport/library failure; no reconnect'
    finally:
        result.update(anonymous_candidate_records=len(accepted),quarantined_candidate_records=len(held),
            groups_completed=group_cursor,groups_total=len(plan['groups']),deferred_fallbacks=len(deferred),
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        reason=result.get('error',result.get('bounded_stop_reason','completed'))
        for flag,checkpoint,rows in [('checkpoint_saved',saved,accepted),('quarantine_checkpoint_saved',quarantined,held)]:
            try:checkpoint.save(rows,result['stages'],finished=True,reason=reason);result[flag]=True
            except Exception:result[flag]=False
        with report.open('x') as f:json.dump(result,f,indent=2)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('plan','authorization','steam-dll','game-exe','output','result'):p.add_argument('--'+flag,required=True)
    p.add_argument('--interface',required=True,type=int)
    asyncio.run(main(p.parse_args()))
