"""ONE authorized pilot: one session attempt, <=3 list requests >=10 s apart.

No reconnection, version guessing loop, EAC changes or game access. Unknown
optional fields use native constructor defaults. Refusal stops the run. Session
cookies/tickets/identity and raw response blobs are never written or printed.
"""
import argparse
import asyncio
import datetime
import hashlib
import json
import struct
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from observe import processes
from budget import PilotBudget
from wire import create_session,message_list,response_header
from steam_ticket import SteamTicket
from transport import SessionTransport
from capture_client_cache import fingerprint,semantics

TARGETS=[('known_cave',(31030,3103001),0x1f030000),
         ('known_outdoor',(6042370,6100002),0x3c2a2500),
         ('new_catacombs',(30020,3002001),0x1e020000)]


def session_response(data):
    r=response_header(data,1,0)
    r.take(4)  # player ID, discarded
    r.vector(256);r.vector(256)  # external identity/IP, discarded
    r.take(8)  # session identifier discarded
    valid_from=r.number('q');valid_until=r.number('q')
    cookie=r.vector(4096);redirect=r.vector(4096)
    if r.offset!=len(data):raise ValueError('Session response schema mismatch')
    if not cookie:raise ValueError('Session cookie missing')
    if redirect:raise RuntimeError('Official redirect requires separate protocol validation')
    # Never export session IDs, cookies or absolute timestamps. Only retain a
    # relative lifetime if both numbers plausibly are Unix seconds; otherwise
    # their semantics remain unknown, without guessing units.
    now=time.time()
    if now-7*86400<=valid_from<=now+300 and now-300<valid_until<=now+7*86400 and valid_until>valid_from:
        return dict(lifetime_metadata_available=True,lifetime_seconds=valid_until-valid_from,
            remaining_seconds_at_auth=max(0,int(valid_until-now)))
    return dict(lifetime_metadata_available=False)


def message_response(data,sequence,expected_map,expected_pair=None,expected_targets=None,include_routes=False):
    if expected_targets is not None:
        if not 1<=len(expected_targets)<=8 or expected_pair is not None:
            raise ValueError('One bounded explicit target routing table required')
        routing={tuple(pair):set(maps) for pair,maps in expected_targets.items()}
        if any(len(pair)!=2 or not maps for pair,maps in routing.items()):
            raise ValueError('Nonempty per-pair map allowlist required')
    else:routing=None
    r=response_header(data,sequence,18);count=r.number('I')
    if count>4096:raise ValueError('Response entry budget')
    records=[];other_maps={};other_pairs={};missing_payload_areas=0;pair_counts={};routes=[]
    for _ in range(count):
        r.take(16)  # player ID, character ID and original message key discarded
        good,poor=r.number('i'),r.number('i');raw=r.vector(4096)
        play_region,area=r.number('I'),r.number('I')
        groups=r.number('I')
        if groups>16:raise ValueError('Group vector budget')
        for _ in range(groups):r.vector(256)
        if len(raw)!=0x208 or struct.unpack_from('<2I',raw)!=(10,512):
            raise ValueError('Message blob schema mismatch')
        payload=memoryview(raw)[8:]
        map_id,secondary=struct.unpack_from('<2I',payload,0x1c0)
        phrase=struct.unpack_from('<8H',payload,0x1d8)
        value=dict(map=map_id,area=area,secondary_area=secondary,
            position=list(struct.unpack_from('<3f',payload,0x1c8)),
            yaw=struct.unpack_from('<f',payload,0x1d4)[0],template1=phrase[0],word1=phrase[2],
            conjunction=phrase[3],template2=phrase[4],word2=phrase[5],
            good=min(9999,max(0,good)),poor=min(9999,max(0,poor)))
        value=semantics(value)
        pair=(play_region,area)
        if expected_pair is not None or routing is not None:
            if (routing is not None and pair not in routing) or (expected_pair is not None and pair!=tuple(expected_pair)):
                key=f'{play_region}:{area}';other_pairs[key]=other_pairs.get(key,0)+1
            payload_area=struct.unpack_from('<I',payload,0x1f8)[0]
            if payload_area and payload_area!=area:raise ValueError('Payload/outer area mismatch')
            if not payload_area:missing_payload_areas+=1
        allowed_maps=routing.get(pair,set()) if routing is not None else ({expected_map} if isinstance(expected_map,int) else set(expected_map))
        if map_id not in allowed_maps:other_maps[str(map_id)]=other_maps.get(str(map_id),0)+1
        key=f'{play_region}:{area}';pair_counts[key]=pair_counts.get(key,0)+1
        key=fingerprint(value)
        records.append(dict(candidate_key=key,**value))
        if include_routes:routes.append(dict(candidate_key=key,pair=[play_region,area]))
    if r.offset!=len(data):raise ValueError('Message response trailing bytes')
    summary=dict(returned_entries=count,unexpected_map_counts=other_maps,
        unexpected_pair_counts=other_pairs,missing_payload_areas=missing_payload_areas)
    if routing is not None:summary['entries_per_pair']=pair_counts
    if include_routes:summary['row_routes']=routes
    return records,summary


async def main(a):
    if any(name.lower()=='eldenring.exe' or 'easyanticheat' in name.lower() or name.lower()=='start_protected_game.exe' for _,name in processes()):
        raise RuntimeError('Normal game/EAC exit required before independent pilot')
    private=ROOT/'build/research/protocol-private'
    output=Path(a.output).resolve()
    if not output.is_relative_to(ROOT/'build/capture') or output.exists():raise ValueError('New private candidate output required')
    budget=PilotBudget(private/'authorized-pilot-ledger.json')
    if budget.state['session_attempts']:raise RuntimeError('This pilot has already attempted a session; no automatic retry')
    magic=json.loads((private/'session-math-v1.json').read_text())['first_three_session_fields']
    ips=[x['data'] for x in json.loads((private/'dns-public-answer.json').read_text())['Answer'] if x['type']==1]
    result=dict(type='limited_protocol_pilot',message_list_requests=0,source_verified=False,
                game_memory_access=False,ticket_or_identity_exported=False,stages=[])
    steam=SteamTicket(a.steam_dll);transport=SessionTransport(ips[0],a.interface,private)
    candidates=[]
    try:
        ticket=steam.acquire();result['stages'].append('Steam encrypted ticket received in memory')
        await transport.open();result['stages'].append('Official TLS/WSS bootstrap and KX complete')
        # Version is the native default, not an invented conversion of App/Regulation.
        request=create_session(1,magic,0,ticket)
        budget.reserve('session');await transport.send(request);del request,ticket
        session_response(await transport.receive());result['stages'].append('Official session response validated')
        last=0
        for n,(label,pair,expected_map) in enumerate(TARGETS,2):
            if last:await asyncio.sleep(max(0,10-(time.monotonic()-last)))
            budget.reserve('message_list');last=time.monotonic()
            result['message_list_requests']+=1
            await transport.send(message_list(n,[pair]))
            records,summary=message_response(await transport.receive(),n,expected_map)
            result['stages'].append(dict(target=label,requested_pair=pair,**summary))
            candidates.extend(records)
            # Do not keep trying cross-region queries after evidence of a wrong mapping.
            if summary['unexpected_map_counts']:raise RuntimeError('Returned map differs from target; pilot stopped')
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x',encoding='utf-8') as f:json.dump(dict(type='unverified_independent_protocol_candidates',
            official_samples=0,records=candidates,warning='Needs target/map/native UI correspondence before promotion'),f,indent=2,allow_nan=False)
        result['anonymous_candidate_records']=len(candidates)
    except Exception as e:
        result['error_type']=type(e).__name__
        # Only our own fixed errors or numeric RPC result are exported.
        result['error']=str(e) if isinstance(e,(RuntimeError,ValueError,TimeoutError)) else 'Transport/library failure; no automatic retry'
    finally:
        try:await transport.close()
        except Exception:result['close_note']='Transport close failed after termination'
        steam.close()
        result['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        (ROOT/'evidence/protocol-pilot-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))


if __name__=='__main__':
    raise SystemExit('Historical pilot is spent and disabled. Do not reset its ledger. Use separately authorized corrected tooling.')
