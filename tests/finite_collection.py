"""Offline-only authorization, inventory and cohort gate regression checks."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/protocol_pilot')]
from finite_budget import FiniteBudget
from build_query_manifest import build
from review_protocol_cohort import review
from reply_policy import disposition
from review_protocol_batch import review as review_batch
from build_mapinfo_query_manifest import palette_regions


class CollectionTests(unittest.TestCase):
    def test_dlc_palette_height_branches_and_unknown_modes(self):
        self.assertEqual(palette_regions(dict(multiPlayAreaId=6100002),60),[6100002])
        fields=dict(multiPlayAreaId=-1,unknown_0x10=1,unknownPlayRegion_1=6810000,unknownPlayRegion_2=6900000)
        self.assertEqual(palette_regions(fields,61),[6810000,6900000])
        fields['unknown_0x10']=2
        with self.assertRaises(ValueError):palette_regions(fields,61)

    def test_partial_batch_keeps_only_completed_matching_responses(self):
        paths=['build/capture/protocol-finite-candidates-v4.json','evidence/protocol-finite-result-v4.json',
               'build/research/world-query-manifest-v2.json','evidence/protocol-cohort-reviewed-result-v3.json']
        if any(not (ROOT/p).exists() for p in paths):self.skipTest('Optional private historical evidence not in source archive')
        args=[json.loads((ROOT/p).read_text(encoding='utf-8')) for p in paths]
        pack,report=review_batch(*args)
        self.assertEqual(len(pack['messages']),1542)
        self.assertEqual(report['accepted_targets'],64)
        self.assertEqual(report['failed_targets'],1)
        self.assertFalse(report['gameplay_acceptance'])
        broken=copy.deepcopy(args);broken[0]['records'][0]['area']=99
        with self.assertRaises(ValueError):review_batch(*broken)
        broken=copy.deepcopy(args);broken[0]['records'].append(broken[0]['records'][0])
        with self.assertRaises(ValueError):review_batch(*broken)
    def test_map_quarantine_does_not_relax_area_or_unknown_map_checks(self):
        summary=dict(unexpected_pair_counts={},unexpected_map_counts={'201785344':11})
        with self.assertRaises(RuntimeError):disposition(summary)
        policy=dict(map_association_policy='quarantine_known_asset_map_mismatch_continue',known_asset_map_ids=[201785344])
        self.assertEqual(disposition(summary,policy),'quarantined_map_association')
        bad=copy.deepcopy(summary);bad['unexpected_pair_counts']={'1:2':1}
        with self.assertRaises(RuntimeError):disposition(bad,policy)
        bad=copy.deepcopy(summary);bad['unexpected_map_counts']={'123':1}
        with self.assertRaises(RuntimeError):disposition(bad,policy)

    def test_manifest_deduplicates_indoor_regions_keeps_outdoor_gaps(self):
        maps=[dict(path='m30_02_00_00.msb.dcx',collision_play_regions=[3002001],msb_sha256='a'),
              dict(path='m30_02_01_00.msb.dcx',collision_play_regions=[3002001],msb_sha256='b'),
              dict(path='m60_42_37_00.msb.dcx',collision_play_regions=[],msb_sha256='c'),
              dict(path='m60_21_18_02.msb.dcx',collision_play_regions=[6100002],msb_sha256='d')]
        result=build(maps,{3002001,6100002},[])
        self.assertEqual(result['target_count'],1)
        self.assertEqual(len(result['targets'][0]['expected_maps']),2)
        self.assertIn('m60_42_37_00',result['canonical_maps_without_direct_collision_target'])
        self.assertEqual(result['enabled_rows_without_target'],[6100002])
        self.assertFalse(result['full_world_coverage'])

    def test_finite_scope_requires_approval_digest_and_preserved_history(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); ledger=root/'ledger.json'; auth=root/'auth.json'; manifest=root/'manifest.json'
            manifest.write_text(json.dumps(dict(targets=[{},{}],target_count=2)))
            approval=dict(action='ONE_FINITE_READONLY_MANIFEST',approved_by_user=False,
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                baseline_session_attempts=3,baseline_list_attempts=5,
                total_session_attempt_limit=4,total_message_list_limit=7,minimum_list_interval_seconds=10)
            ledger.write_text(json.dumps(dict(session_attempts=3,message_list_attempts=5,last_list_time=100,events=[])))
            auth.write_text(json.dumps(approval))
            with self.assertRaises(RuntimeError):FiniteBudget(ledger,auth,manifest)
            approval['approved_by_user']=True; auth.write_text(json.dumps(approval))
            first=FiniteBudget(ledger,auth,manifest); stale=FiniteBudget(ledger,auth,manifest)
            with self.assertRaises(RuntimeError):first.reserve('message_list',110)
            first.reserve('session',101)
            with self.assertRaises(RuntimeError):stale.reserve('session',102)
            first.reserve('message_list',110)
            with self.assertRaises(RuntimeError):first.reserve('message_list',119)
            first.reserve('message_list',120)
            with self.assertRaises(RuntimeError):first.reserve('message_list',130)
            with self.assertRaises(RuntimeError):FiniteBudget(ledger,auth,manifest)
            self.assertEqual(json.loads(ledger.read_text())['session_attempts'],4)

    def test_remaining_scope_cannot_reset_or_expand_after_approval(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ledger=root/'ledger.json';auth=root/'approval.json';manifest=root/'manifest.json'
            manifest.write_text(json.dumps(dict(targets=[{}]*621,target_count=621)))
            ledger.write_text(json.dumps(dict(session_attempts=4,message_list_attempts=70,last_list_time=100,events=[])))
            approval=dict(action='ONE_FINITE_READONLY_MANIFEST',approved_by_user=True,
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),baseline_session_attempts=4,
                baseline_list_attempts=70,total_session_attempt_limit=5,total_message_list_limit=691,
                minimum_list_interval_seconds=10)
            auth.write_text(json.dumps(approval));budget=FiniteBudget(ledger,auth,manifest)
            budget.reserve('session',101);budget.reserve('message_list',110)
            state=json.loads(ledger.read_text());self.assertEqual((state['session_attempts'],state['message_list_attempts']),(5,71))
            with self.assertRaises(RuntimeError):FiniteBudget(ledger,auth,manifest)
            ledger.write_text(json.dumps(dict(session_attempts=4,message_list_attempts=70,last_list_time=100,events=[])))
            manifest.write_text(json.dumps(dict(targets=[{}]*622,target_count=622)))
            with self.assertRaises(RuntimeError):FiniteBudget(ledger,auth,manifest)

    def test_actual_cohort_witness_and_tamper_gates(self):
        if not (ROOT/'build/capture/protocol-routed-candidates-v3.json').exists():
            self.skipTest('Optional private historical evidence not in source archive')
        load=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
        args=[load(p) for p in ['build/capture/protocol-routed-candidates-v3.json',
            'evidence/protocol-routed-result-v3.json','build/capture/protocol-stormfoot-native-v3.json',
            'build/capture/protocol-new-region-waiting-v3.json','evidence/protocol-cohort-review-v3.json']]
        pack,report=review(*args)
        self.assertEqual(len(pack['messages']),71)
        self.assertEqual(pack['source_type'],'official_protocol_sample')
        self.assertEqual(report['individually_offline_ui_matched'],1)
        broken=copy.deepcopy(args);broken[4]['ui_total_appraisals']=6
        with self.assertRaises(ValueError):review(*broken)
        broken=copy.deepcopy(args);broken[2]['offline']['online']=1
        with self.assertRaises(ValueError):review(*broken)


if __name__=='__main__':unittest.main()
