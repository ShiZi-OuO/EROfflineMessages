"""Prepared correction; cannot run without NEW explicit one-attempt approval.

Original RPC ledger retained. One more session (two total), <=3 message lists
TOTAL >=10 s apart. No modified client, injection, EAC changes or reconnects.
Known fields come from exact-file analysis and strict offline fixed getters.
Unknown tail fields retain native constructor defaults, not guessed metrics.
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
from corrected_budget import CorrectedBudget
from routed_budget import RoutedBudget
from finite_budget import FiniteBudget
from wire import create_session,message_list,response_header
from steam_ticket import SteamTicket
from transport import SessionTransport,HOST
from run_pilot import session_response,message_response
from native_region_pair import native_pair
from rpc_frames import await_response,CandidateCheckpoint
from reply_policy import disposition

TARGETS=[('known_cave',native_pair(3103001,0x1f030000),0x1f030000),
         ('known_capital',native_pair(1105092,0x0b050000),0x0b050000),
         ('new_stormfoot',native_pair(3002001,0x1e020000),0x1e020000)]
ROUTED_TARGETS=[TARGETS[0],('known_outdoor',native_pair(6100002,0x3c2a2500),0x3c2a2500),TARGETS[2]]


async def main(a):
    private=ROOT/'build/research/protocol-private'
    if a.batch_manifest:
        budget=FiniteBudget(private/'authorized-pilot-ledger.json',a.authorization,a.batch_manifest)
        manifest=json.loads(Path(a.batch_manifest).read_text())
        targets=[(t['id'],tuple(t['pair']),set(t['expected_maps'])) for t in manifest['targets']]
        if len({t[0] for t in targets})!=len(targets):raise ValueError('Duplicate manifest target')
        for _,pair,maps in targets:
            if not maps or any(native_pair(pair[1],m)!=pair for m in maps):raise ValueError('Native area conversion mismatch')
    else:
        budget=(RoutedBudget if a.routed_validation else CorrectedBudget)(private/'authorized-pilot-ledger.json',a.authorization)
        targets=ROUTED_TARGETS if a.routed_validation else TARGETS
    if any(name.lower()=='eldenring.exe' or 'easyanticheat' in name.lower() or name.lower()=='start_protected_game.exe' for _,name in processes()):
        raise RuntimeError('Normal game/EAC exit required')
    output=Path(a.output).resolve();report=Path(a.result).resolve()
    if not output.is_relative_to(ROOT/'build/capture') or output.exists():raise ValueError('New private candidates required')
    if not report.is_relative_to(ROOT/'evidence') or report.exists():raise ValueError('New evidence report required')
    sha=hashlib.sha256(Path(a.game_exe).read_bytes()).hexdigest()
    proof=json.loads((ROOT/'evidence/static-session-version-v2.json').read_text())
    fields=json.loads((private/'session-known-fields-v2.json').read_text())
    if sha!=proof['game_sha256'] or sha!=fields['game_sha256'] or fields['network_version']!=proof['network_version'] or proof['network_version']!=1172:
        raise ValueError('Exact-image static version proof mismatch')
    wireproof=json.loads((ROOT/'evidence/protocol-pilot-native-wire-v2-1172.json').read_text())
    if not wireproof['byte_for_byte_match'] or wireproof['version_argument']!=1172:raise ValueError('Corrected native layout proof missing')
    magic=json.loads((private/'session-math-v1.json').read_text())['first_three_session_fields']
    # Public DNS only, no game/account fields sent here. No cached-IP assumption.
    dns=json.loads(urllib.request.urlopen('https://dns.google/resolve?name='+HOST+'&type=A',timeout=15).read())
    ips=[r['data'] for r in dns.get('Answer',[]) if r['type']==1]
    if not ips:raise RuntimeError('Official endpoint DNS unavailable; no authentication sent')
    result=dict(type='one_finite_readonly_manifest' if a.batch_manifest else ('one_routed_readonly_validation' if a.routed_validation else 'one_corrected_independent_protocol_pilot'),network_version=1172,
        message_list_requests=0,session_rpc_success=False,source_verified=False,
        game_memory_access=False,ticket_or_identity_exported=False,stages=[],
        previous_ledger_preserved=True,unverified_tail_defaults=True)
    steam=SteamTicket(a.steam_dll);transport=SessionTransport(ips[0],a.interface,private)
    candidates=[];frames=[];completed=set();checkpoint=CandidateCheckpoint(output)
    quarantine=[];quarantine_checkpoint=None
    if a.batch_manifest and manifest.get('map_association_policy')=='quarantine_known_asset_map_mismatch_continue':
        quarantine_checkpoint=CandidateCheckpoint(output.with_name(output.stem+'-quarantine.json'))
        result['manifest_sha256']=hashlib.sha256(Path(a.batch_manifest).read_bytes()).hexdigest()
    result['asynchronous_frames']=frames
    try:
        ticket=steam.acquire();result['stages'].append('Genuine Steam encrypted ticket received in memory')
        # Spend this session before opening its socket: even an incomplete TLS
        # connection must not leave an accidentally reusable no-reconnect scope.
        budget.reserve('session')
        await transport.open();result['stages'].append('Official TLS/WSS bootstrap and KX complete')
        # The legacy encoder keyword names were provisional. Exact native field
        # offsets are used here: 80=NAT, 88=mapped locale, 8c=mapped region.
        request=create_session(1,magic,fields['network_version'],ticket,
            platform=fields['field80'],region=fields['field88'],language=fields['field8c'],
            cross_region=fields['boolean84'],flags=fields['boolean90'],tail=tuple(fields['tail']))
        await transport.send(request);del ticket,request
        raw=await await_response(transport,1,0,frames,completed);completed.add(1)
        result['session_rpc_success']=True
        session_response(raw);del raw
        result['stages'].append('Session response schema validated; no unsupported redirect')
        last=0
        for sequence,(label,pair,expected_map) in enumerate(targets,2):
            if last:await asyncio.sleep(max(0,10-(time.monotonic()-last)))
            budget.reserve('message_list');last=time.monotonic();result['message_list_requests']+=1
            await transport.send(message_list(sequence,[pair]))
            raw=await await_response(transport,sequence,18,frames,completed);completed.add(sequence)
            records,summary=message_response(raw,sequence,expected_map,expected_pair=pair);del raw
            stage=dict(target=label,requested_pair=pair,**summary)
            result['stages'].append(stage)
            mode=disposition(summary,manifest if a.batch_manifest else None)
            stage['disposition']=mode
            if mode=='quarantined_map_association':
                quarantine.extend(records)
                quarantine_checkpoint.save(quarantine,result['stages'])
                checkpoint.save(candidates,result['stages'])
                continue
            candidates.extend(records);checkpoint.save(candidates,result['stages'])
    except Exception as error:
        result['error_type']=type(error).__name__
        result['error']=str(error) if isinstance(error,(RuntimeError,ValueError,TimeoutError)) else 'Transport/library failure; no automatic retry'
    finally:
        try:await transport.close()
        except Exception:result['close_note']='Transport close failed after termination'
        steam.close();result['anonymous_candidate_records']=len(candidates)
        result['quarantined_candidate_records']=len(quarantine)
        if quarantine_checkpoint:
            try:
                quarantine_checkpoint.save(quarantine,result['stages'],finished=True,reason=result.get('error','completed'))
                result['quarantine_checkpoint_saved']=True
            except Exception:
                result['quarantine_checkpoint_saved']=False
        try:
            checkpoint.save(candidates,result['stages'],finished=True,reason=result.get('error','completed'))
            result['checkpoint_saved']=True
        except Exception:
            result['checkpoint_saved']=False
            result['checkpoint_note']='Final checkpoint failed; earlier atomic checkpoints retained'
        result['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with report.open('x') as f:json.dump(result,f,indent=2)
        # Steam's own diagnostics may print identifiers. Invoke with stdout/
        # stderr redirected to a private file, then inspect only this report.


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['authorization','steam-dll','game-exe','output','result']:p.add_argument('--'+name,required=True)
    p.add_argument('--interface',type=int,required=True)
    p.add_argument('--routed-validation',action='store_true',help='NEW 3-session/5-list cumulative authorization required')
    p.add_argument('--batch-manifest',help='Separate explicit hash-bound finite manifest authorization required; no reconnect')
    asyncio.run(main(p.parse_args()))
