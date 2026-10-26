"""Synthetic-only scope, failure transition, partition and audit tests."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/protocol_pilot'),str(ROOT/'tests')]
from campaign_budget import CampaignBudget
from run_campaign import partition_response,validate_plan
from review_campaign_protocol import review
from grouped_review import row


class CampaignTests(unittest.TestCase):
    def budget(self,root,approved=True):
        plan=root/'plan.json';auth=root/'approval.json';ledger=root/'ledger.json'
        plan.write_bytes((ROOT/'build/research/canonical-campaign-plan-v8.json').read_bytes())
        approval=json.loads((ROOT/'evidence/canonical-campaign-authorization-v8.pending.json').read_text())
        approval['approved_by_user']=approved;approval['user_authorization']='授权上述固定清单和两段上限'
        auth.write_text(json.dumps(approval,ensure_ascii=False),encoding='utf-8')
        ledger.write_text(json.dumps(dict(session_attempts=6,message_list_attempts=479,last_list_time=0,events=[])))
        return ledger,auth,plan

    def test_pending_approval_rejected_and_plan_hash_bound(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.budget(Path(d),False)
            with self.assertRaises(RuntimeError):CampaignBudget(*args)
            args=self.budget(Path(d));args[2].write_text(args[2].read_text()+' ')
            with self.assertRaises(RuntimeError):CampaignBudget(*args)

    def test_failure_forbids_second_segment_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.budget(Path(d));b=CampaignBudget(*args);stale=CampaignBudget(*args)
            b.reserve('session',100);b.reserve('message_list',110)
            with self.assertRaises(RuntimeError):b.reserve('message_list',119)
            b.reserve('segment_failed_close',120)
            with self.assertRaises(RuntimeError):stale.reserve('session',130)
            with self.assertRaises(RuntimeError):b.reserve('message_list',130)
            with self.assertRaises(RuntimeError):CampaignBudget(*args)

    def test_normal_segments_preserve_caps(self):
        with tempfile.TemporaryDirectory() as d:
            b=CampaignBudget(*self.budget(Path(d)));b.reserve('session',1)
            for i in range(250):b.reserve('message_list',10+i*10)
            with self.assertRaises(RuntimeError):b.reserve('message_list',2510)
            b.reserve('segment_normal_close',2510);b.reserve('session',2520)
            for i in range(250):b.reserve('message_list',2530+i*10)
            with self.assertRaises(RuntimeError):b.reserve('message_list',5040)
            b.reserve('segment_normal_close',5040)
            with self.assertRaises(RuntimeError):b.reserve('session',5050)
            self.assertEqual((b.state['session_attempts'],b.state['message_list_attempts']),(8,979))

    def fixtures(self):
        controls=[dict(id='c'+str(i),pair=[3002001,3002001],expected_maps=[0x1e020000]) for i in range(3)]
        target=dict(id='w',pair=[6042370,6100002],expected_maps=[0x3c2a2500])
        plan=dict(controls=controls,targets=[target],groups=[dict(id='world-group-001',target_ids=['w'])])
        stages=[];rows=[];qs=[]
        for index in (1,2):
            for c in controls:
                r=row(0x1e020000,3002001);route=dict(candidate_key=r['candidate_key'],pair=c['pair'])
                stages.append(dict(session_index=index,query='known-control-'+c['id'],target_ids=[c['id']],requested_pairs=[c['pair']],fallback=False,
                    returned_entries=1,unexpected_pair_counts={},unexpected_map_counts={},entries_per_pair={'3002001:3002001':1},row_routes=[route],
                    accepted_entries=1,quarantined_entries=0,accepted_row_routes=[route],accepted_pair_counts={'3002001:3002001':1},disposition='accepted'))
                rows.append(r)
        good=row(0x3c2a2500,6100002);bad=row(0x3c2a2510,6100002)
        routes=[dict(candidate_key=r['candidate_key'],pair=target['pair']) for r in (good,bad)]
        summary=dict(returned_entries=2,unexpected_pair_counts={},unexpected_map_counts={str(bad['map']):1},entries_per_pair={'6042370:6100002':2},row_routes=routes)
        keep,q,details=partition_response([good,bad],summary,{tuple(target['pair']):set(target['expected_maps'])})
        stages.append(dict(session_index=2,query='world-group-001',target_ids=['w'],requested_pairs=[target['pair']],fallback=False,**summary,**details))
        rows.extend(keep);qs.extend(q)
        cp=dict(finished=True,stages=stages,records=rows);qp=dict(finished=True,stages=stages,records=qs)
        receipt=dict(session_rpc_success=True,checkpoint_saved=True,quarantine_checkpoint_saved=True,stages=stages,
            anonymous_candidate_records=len(rows),quarantined_candidate_records=len(qs),message_list_requests=7,
            attempted_queries=[{k:s[k] for k in ('query','session_index','target_ids','fallback')} for s in stages],
            segments=[dict(normal_close_reason='Planned cap'),dict(normal_close_reason='Completed')])
        return cp,qp,receipt,plan,dict(individually_offline_ui_matched=1)

    def test_per_row_quarantine_and_two_session_audit(self):
        pack,report=review(*self.fixtures())
        self.assertEqual(len(pack['messages']),2);self.assertEqual(report['quarantined_records'],1)
        self.assertFalse(report['gameplay_acceptance'])
        self.assertNotIn(0x3c2a2510,[r['map'] for r in pack['messages']])

    def test_wrong_area_and_quarantine_tampering_fail(self):
        args=self.fixtures();args[2]['segments'][0].pop('normal_close_reason')
        with self.assertRaises(ValueError):review(*args)
        args=self.fixtures();args[1]['records'][0]['map']=0x3c2a2500
        with self.assertRaises(ValueError):review(*args)
        args=self.fixtures();args[0]['stages'][-1]['unexpected_pair_counts']={'1:2':1}
        with self.assertRaises(ValueError):review(*args)

    def test_real_prepared_plan_is_bounded_partition(self):
        plan=json.loads((ROOT/'build/research/canonical-campaign-plan-v8.json').read_text())
        self.assertEqual(len(validate_plan(plan)),854)
        self.assertEqual(len(plan['groups']),426)

    def test_failed_last_request_preserves_earlier_samples(self):
        args=self.fixtures();receipt=args[2]
        receipt['error']='Official RPC error 20000';receipt['message_list_requests']+=1
        receipt['attempted_queries'].append(dict(query='fallback-w',session_index=2,target_ids=['w'],fallback=True))
        pack,report=review(*args)
        self.assertEqual(len(pack['messages']),2);self.assertTrue(report['stopped_early'])


if __name__=='__main__':unittest.main()
