"""PREPARED: separately authorized grouped world queries; never auto reconnect.

Invoke only with stdout/stderr redirected to a private file: the original Steam
library can print account diagnostics. Tickets/identities/raw blobs stay out of
candidate checkpoints and public reports. No game injection or EAC changes.
"""
import argparse
import asyncio
import datetime
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from observe import processes
from group_budget import GroupBudget
from wire import create_session,message_list
from steam_ticket import SteamTicket
from transport import SessionTransport,HOST
from run_pilot import session_response,message_response
from native_region_pair import native_pair
from rpc_frames import await_response,CandidateCheckpoint
from reply_policy import disposition


def require_game_closed():
    if any(n.lower() in ('eldenring.exe','start_protected_game.exe') or 'easyanticheat' in n.lower() for _,n in processes()):
        raise RuntimeError('Game/EAC must remain normally exited during independent collection')


class CollectionLimitReached(Exception):pass


async def main(a):
    private=ROOT/'build/research/protocol-private'
    budget=GroupBudget(private/'authorized-pilot-ledger.json',a.authorization,a.plan)
    prerequisite=json.loads((ROOT/'evidence/protocol-finite-result-v5.json').read_text())
    approval=json.loads(Path(a.authorization).read_text())
    recovery=approval.get('action')=='ONE_GROUPED_RECOVERY_COLLECTION'
    valid_prerequisite=(prerequisite.get('error')=='Official RPC error 20000'
        and prerequisite.get('message_list_requests')==360) if recovery else (
        not prerequisite.get('error') and prerequisite.get('message_list_requests')==621)
    if (not valid_prerequisite or prerequisite.get('session_rpc_success') is not True
            or prerequisite.get('checkpoint_saved') is not True
            or any(f.get('kind')!=7 for f in prerequisite.get('asynchronous_frames',[]))):
        raise RuntimeError('Current 621-query batch must complete normally before this separately authorized phase')
    plan=json.loads(Path(a.plan).read_text())
    controls=plan['controls'];targets=plan['targets']
    all_targets={t['id']:t for t in controls+targets}
    if len(all_targets)!=len(controls)+len(targets):raise ValueError('Duplicate grouped target IDs')
    if len(targets)!=plan['new_target_count']:raise ValueError('Grouped target count changed')
    grouped_ids=[i for g in plan['groups'] for i in g['target_ids']]
    if len(grouped_ids)!=len(set(grouped_ids)) or set(grouped_ids)!={t['id'] for t in targets}:
        raise ValueError('Groups must partition all new targets exactly once')
    if any(not 1<=len(g['target_ids'])<=8 for g in plan['groups']):raise ValueError('Group vector budget')
    algorithmic_maximum=1+len(plan['groups'])+len(controls)+len(targets)
    if plan.get('uncapped_maximum_list_queries',plan['maximum_list_queries'])!=algorithmic_maximum:
        raise ValueError('Fallback budget changed')
    if not 1<=plan['maximum_list_queries']<=algorithmic_maximum:raise ValueError('Invalid request cap')
    for t in all_targets.values():
        if not t['expected_maps'] or any(native_pair(t['pair'][1],m)!=tuple(t['pair']) for m in t['expected_maps']):
            raise ValueError('Native area conversion mismatch')
    output=Path(a.output).resolve();report=Path(a.result).resolve()
    if not output.is_relative_to(ROOT/'build/capture') or output.exists():raise ValueError('New private candidate path required')
    if not report.is_relative_to(ROOT/'evidence') or report.exists():raise ValueError('New sanitized report path required')
    require_game_closed()
    proof=json.loads((ROOT/'evidence/static-session-version-v2.json').read_text())
    fields=json.loads((private/'session-known-fields-v2.json').read_text())
    sha=hashlib.sha256(Path(a.game_exe).read_bytes()).hexdigest()
    if sha!=proof['game_sha256'] or sha!=fields['game_sha256'] or fields['network_version']!=1172:
        raise ValueError('Exact-image version proof mismatch')
    magic=json.loads((private/'session-math-v1.json').read_text())['first_three_session_fields']
    dns=json.loads(urllib.request.urlopen('https://dns.google/resolve?name='+HOST+'&type=A',timeout=15).read())
    ips=[r['data'] for r in dns.get('Answer',[]) if r['type']==1]
    if not ips:raise RuntimeError('Official endpoint DNS unavailable')
    result=dict(type='one_grouped_world_collection',plan_sha256=hashlib.sha256(Path(a.plan).read_bytes()).hexdigest(),
        session_rpc_success=False,message_list_requests=0,fallback_requests=0,maximum_list_queries=plan['maximum_list_queries'],
        stages=[],asynchronous_frames=[],game_memory_access=False,ticket_or_identity_exported=False)
    candidates=[];quarantine=[];completed=set();fallback_used=set();sequence=1;last=0
    session_started=None;session_cap=plan.get('maximum_session_seconds',86400)
    saved=CandidateCheckpoint(output,50000)
    held=CandidateCheckpoint(output.with_name(output.stem+'-quarantine.json'),50000)
    steam=SteamTicket(a.steam_dll);transport=SessionTransport(ips[0],a.interface,private)

    async def query(label,items,fallback=False):
        nonlocal sequence,last
        if result['message_list_requests']>=plan['maximum_list_queries']:
            raise CollectionLimitReached('Explicit list request cap reached')
        if session_started is not None and time.monotonic()-session_started>=session_cap-30:
            raise CollectionLimitReached('Explicit session duration cap reached; no reconnect')
        if last:await asyncio.sleep(max(0,10-(time.monotonic()-last)))
        else:await asyncio.sleep(max(0,10-(time.time()-budget.state['last_list_time'])))
        require_game_closed()
        if session_started is not None and time.monotonic()-session_started>=session_cap-30:
            raise CollectionLimitReached('Explicit session duration cap reached after rate wait')
        if fallback:
            if len(items)!=1 or items[0]['id'] in fallback_used:raise RuntimeError('Single-target fallback already spent')
            fallback_used.add(items[0]['id']);result['fallback_requests']+=1
        sequence+=1
        pairs=[tuple(t['pair']) for t in items]
        routing={tuple(t['pair']):set(t['expected_maps']) for t in items}
        budget.reserve('message_list');last=time.monotonic();result['message_list_requests']+=1
        await transport.send(message_list(sequence,pairs))
        raw=await await_response(transport,sequence,18,result['asynchronous_frames'],completed);completed.add(sequence)
        rows,summary=message_response(raw,sequence,None,expected_targets=routing);del raw
        stage=dict(query=label,target_ids=[t['id'] for t in items],requested_pairs=pairs,fallback=fallback,**summary)
        result['stages'].append(stage)
        mode=disposition(summary,plan);stage['disposition']=mode
        if mode=='quarantined_map_association':
            quarantine.extend(rows);held.save(quarantine,result['stages'])
            hits=set()
        else:
            candidates.extend(rows)
            hits={pair for pair in pairs if summary['entries_per_pair'].get(f'{pair[0]}:{pair[1]}',0)}
        saved.save(candidates,result['stages'])
        return [t for t in items if tuple(t['pair']) not in hits]

    try:
        ticket=steam.acquire();result['stages'].append('Genuine Steam encrypted ticket received in memory')
        budget.reserve('session');session_started=time.monotonic();await transport.open()
        result['stages'].append('Official TLS/WSS bootstrap and KX complete')
        request=create_session(1,magic,1172,ticket,platform=fields['field80'],region=fields['field88'],
            language=fields['field8c'],cross_region=fields['boolean84'],flags=fields['boolean90'],tail=tuple(fields['tail']))
        await transport.send(request);del request,ticket
        raw=await await_response(transport,1,0,result['asynchronous_frames'],completed);completed.add(1)
        result['session_lifetime_metadata']=session_response(raw);del raw;result['session_rpc_success']=True
        metadata=result['session_lifetime_metadata']
        if metadata.get('lifetime_metadata_available'):
            session_cap=min(session_cap,max(0,metadata['remaining_seconds_at_auth']-120))
        missing=await query('known-control-three',controls)
        for t in missing:
            if await query('control-fallback-'+t['id'],[t],True):
                raise RuntimeError('Known control remains empty/quarantined; grouped semantics inconclusive; expansion not sent')
        result['control_routes_verified']=True
        deferred=[]
        for group in plan['groups']:
            items=[all_targets[i] for i in group['target_ids']]
            missing=await query(group['id'],items)
            if plan.get('fallback_scheduling')=='after_all_groups':deferred.extend(missing)
            else:
                for t in missing:await query('fallback-'+t['id'],[t],True)
        for t in deferred:await query('fallback-'+t['id'],[t],True)
    except CollectionLimitReached as error:
        result['bounded_stop_reason']=str(error)
    except Exception as error:
        result['error_type']=type(error).__name__
        result['error']=str(error) if isinstance(error,(RuntimeError,ValueError,TimeoutError)) else 'Transport/library failure; stopped without reconnect'
    finally:
        try:await transport.close()
        except Exception:result['close_note']='Transport close failed after termination'
        steam.close()
        result['anonymous_candidate_records']=len(candidates);result['quarantined_candidate_records']=len(quarantine)
        for name,checkpoint,rows in [('checkpoint_saved',saved,candidates),('quarantine_checkpoint_saved',held,quarantine)]:
            try:checkpoint.save(rows,result['stages'],finished=True,reason=result.get('error','completed'));result[name]=True
            except Exception:result[name]=False
        result['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        if session_started is not None:result['elapsed_session_seconds']=round(time.monotonic()-session_started,2)
        with report.open('x') as f:json.dump(result,f,indent=2)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('plan','authorization','steam-dll','game-exe','output','result'):p.add_argument('--'+flag,required=True)
    p.add_argument('--interface',required=True,type=int)
    asyncio.run(main(p.parse_args()))
