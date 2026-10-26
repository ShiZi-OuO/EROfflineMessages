"""Execute campaign control flow using only in-memory fake Steam/transport."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools/protocol_pilot'),str(ROOT/'tools'),str(ROOT/'tests')]
import run_campaign as runner
from grouped_review import row
from types import SimpleNamespace


class ExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def execute(self,fail_query=None,fail_close=False,parent=False,gap=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);private=root/'build/research/protocol-private';private.mkdir(parents=True)
            (root/'evidence').mkdir();(root/'build/capture').mkdir()
            exe=root/'game.exe';exe.write_bytes(b'FAKE ONLY')
            import hashlib
            sha=hashlib.sha256(exe.read_bytes()).hexdigest()
            (root/'evidence/static-session-version-v2.json').write_text(json.dumps(dict(game_sha256=sha)))
            fields=dict(game_sha256=sha,network_version=1172,field80=0,field88=0,field8c=0,boolean84=False,boolean90=False,tail=[])
            (private/'session-known-fields-v2.json').write_text(json.dumps(fields))
            (private/'session-math-v1.json').write_text(json.dumps(dict(first_three_session_fields=[0,0,0])))
            plan_name=('gap-recheck-plan-v10.json' if gap else
                       'parent-area-query-plan-v9.json' if parent else 'canonical-campaign-plan-v8.json')
            actual=json.loads((ROOT/'build/research'/plan_name).read_text())
            plan=root/'plan.json';plan.write_text(json.dumps(actual))
            calls=dict(sessions=0,lists=0,closed=0,tickets=0)
            class Budget:
                digest='fake-plan';state=dict(last_list_time=0)
                normal=False
                def __init__(self,*a):pass
                def reserve(self,kind):
                    if kind=='session':
                        if calls['sessions'] and not self.normal:raise AssertionError('Unauthorized reconnect')
                        calls['sessions']+=1;self.normal=False
                    elif kind=='message_list':calls['lists']+=1
                    elif kind=='segment_normal_close':self.normal=True
                    elif kind=='segment_failed_close':self.normal=False
                    else:raise AssertionError(kind)
            class Steam:
                def __init__(self,*a):pass
                def acquire(self):calls['tickets']+=1;return b'FAKE TICKET'
                def close(self):pass
            class Transport:
                def __init__(self,*a):pass
                async def open(self):pass
                async def send(self,request):self.request=request
                async def close(self):
                    calls['closed']+=1
                    if fail_close:raise RuntimeError('fake close failure')
            async def response(transport,sequence,variant,*a):
                if variant==18 and calls['lists']==fail_query:raise RuntimeError('Official RPC error 20000')
                return transport.request
            def decode(raw,sequence,expected,expected_targets,include_routes):
                rows=[];routes=[];counts={}
                for pair,maps in expected_targets.items():
                    r=row(next(iter(maps)),pair[1]);rows.append(r)
                    routes.append(dict(candidate_key=r['candidate_key'],pair=list(pair)))
                    counts[':'.join(map(str,pair))]=1
                return rows,dict(returned_entries=len(rows),row_routes=routes,entries_per_pair=counts,
                    unexpected_map_counts={},unexpected_pair_counts={},missing_payload_areas=0)
            class Checkpoint:
                def __init__(self,*a):pass
                def save(self,*a,**kw):pass
            async def sleep(*a):pass
            dns=SimpleNamespace(read=lambda:b'{"Answer":[{"type":1,"data":"192.0.2.1"}]}')
            args=SimpleNamespace(authorization='FAKE',plan=str(plan),output=str(root/'build/capture/result.json'),
                result=str(root/'evidence/result.json'),game_exe=str(exe),steam_dll='FAKE',interface=16)
            with patch.multiple(runner,ROOT=root,CampaignBudget=Budget,SteamTicket=Steam,SessionTransport=Transport,
                    CandidateCheckpoint=Checkpoint,require_game_closed=lambda:None,await_response=response,
                    message_response=decode,session_response=lambda raw:dict(lifetime_metadata_available=False),
                    create_session=lambda *a,**kw:b'FAKE',message_list=lambda seq,pairs:(seq,pairs)), \
                    patch.object(runner.urllib.request,'urlopen',return_value=dns), \
                    patch.object(runner.asyncio,'sleep',sleep),patch.object(runner.time,'monotonic',return_value=1):
                await runner.main(args)
            return calls,json.loads(Path(args.result).read_text())

    async def test_two_planned_segments_without_duplicate_groups(self):
        calls,result=await self.execute()
        self.assertEqual(calls['sessions'],2);self.assertEqual(calls['lists'],432)
        self.assertTrue(result['all_planned_groups_completed']);self.assertNotIn('error',result)
        groups=[s['query'] for s in result['stages'] if s['query'].startswith('world-group-')]
        self.assertEqual(len(groups),426);self.assertEqual(len(set(groups)),426)
        self.assertLessEqual(max(s['message_list_requests'] for s in result['segments']),250)

    async def test_refusal_keeps_prior_rows_and_never_reconnects(self):
        calls,result=await self.execute(fail_query=4)
        self.assertEqual(calls['sessions'],1);self.assertEqual(calls['lists'],4)
        self.assertEqual(result['anonymous_candidate_records'],3)
        self.assertIn('20000',result['error']);self.assertTrue(result['checkpoint_saved'])

    async def test_failed_normal_close_forbids_second_auth(self):
        calls,result=await self.execute(fail_close=True)
        self.assertEqual(calls['sessions'],1);self.assertIn('next segment forbidden',result['error'])

    async def test_parent_plan_ends_after_one_session_and_22_queries(self):
        calls,result=await self.execute(parent=True)
        self.assertEqual(calls['sessions'],1);self.assertEqual(calls['lists'],22)
        self.assertTrue(result['all_planned_groups_completed']);self.assertEqual(result['fallback_requests'],0)

    async def test_gap_plan_sends_exact_single_targets_without_fallback(self):
        calls,result=await self.execute(gap=True)
        self.assertEqual(calls['sessions'],1);self.assertEqual(calls['lists'],126)
        self.assertTrue(result['all_planned_groups_completed']);self.assertEqual(result['fallback_requests'],0)
        self.assertTrue(all(len(s['requested_pairs'])==1 for s in result['stages']))

    async def test_gap_refusal_stops_without_second_authentication(self):
        calls,result=await self.execute(gap=True,fail_query=5)
        self.assertEqual(calls['sessions'],1);self.assertEqual(calls['lists'],5)
        self.assertIn('20000',result['error']);self.assertEqual(result['anonymous_candidate_records'],4)


if __name__=='__main__':unittest.main()
