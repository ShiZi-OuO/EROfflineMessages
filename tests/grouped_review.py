"""Audit synthetic grouped checkpoints and reject invented/repeated fallbacks."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from review_grouped_protocol import review
from capture_client_cache import fingerprint


def row(map_id,area):
    r=dict(map=map_id,area=area,secondary_area=0,position=[1.,2.,3.],yaw=0.,template1=10000,
        word1=40000,conjunction=0,template2=0,word2=0,good=2,poor=1)
    return dict(candidate_key=fingerprint(r),**r)


def stage(label,target,pair,count,fallback=False):
    return dict(query=label,target_ids=[target],requested_pairs=[pair],fallback=fallback,
        returned_entries=count,unexpected_pair_counts={},unexpected_map_counts={},
        entries_per_pair={':'.join(map(str,pair)):count} if count else {},disposition='accepted')


class ReviewTests(unittest.TestCase):
    def fixtures(self):
        c=dict(id='c',pair=[3002001,3002001],expected_maps=[0x1e020000])
        w=dict(id='w',pair=[6042370,6100002],expected_maps=[0x3c2a2500])
        plan=dict(controls=[c],targets=[w],groups=[dict(id='world-group-001',target_ids=['w'])],known_asset_map_ids=[0x1e020000,0x3c2a2500])
        stages=[stage('known-control-three','c',c['pair'],1),stage('world-group-001','w',w['pair'],0),stage('fallback-w','w',w['pair'],1,True)]
        checkpoint=dict(finished=True,stages=stages,records=[row(0x1e020000,3002001),row(0x3c2a2500,6100002)])
        receipt=dict(session_rpc_success=True,checkpoint_saved=True,stages=stages,anonymous_candidate_records=2,quarantined_candidate_records=0)
        return checkpoint,receipt,plan,dict(individually_offline_ui_matched=1)

    def test_valid_partial_empty_then_one_fallback(self):
        pack,report=review(*self.fixtures())
        self.assertEqual(len(pack['messages']),2)
        self.assertEqual(report['new_targets_with_finite_samples'],1)
        self.assertEqual(report['fallback_queries'],1)
        self.assertFalse(report['gameplay_acceptance'])

    def test_duplicate_fallback_and_unattributed_rows_rejected(self):
        args=self.fixtures();extra=copy.deepcopy(args[0]['stages'][-1]);args[0]['stages'].append(extra)
        with self.assertRaises(ValueError):review(*args)
        args=self.fixtures();args[0]['records'].append(args[0]['records'][0])
        with self.assertRaises(ValueError):review(*args)

    def test_pair_map_cross_wiring_and_counter_tampering_rejected(self):
        args=self.fixtures();args[0]['records'][1]=row(0x1e020000,6100002)
        with self.assertRaises(ValueError):review(*args)
        args=self.fixtures();args[1]['anonymous_candidate_records']=3
        with self.assertRaises(ValueError):review(*args)


if __name__=='__main__':unittest.main()
