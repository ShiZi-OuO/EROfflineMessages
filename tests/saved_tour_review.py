"""Promotion guards: receipt evidence, native witness and map quarantine."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from review_saved_tour import review


class TourReview(unittest.TestCase):
    def setUp(self):
        self.record = dict(map=0x0b050000, area=1105092, secondary_area=11050,
            position=[1., 2., 3.], yaw=0., template1=10015, word1=32031,
            conjunction=0, template2=0, word2=0, good=1, poor=0)
        self.candidate = dict(type='unverified_saved_cache_candidates',
            game_process_access=False, save_writes=0, records=[self.record])
        self.native = dict(sha256='testimage',
            offline=dict(online=0, menu_online_enabled=0, menu_property_initialized=-2),
            items=[dict(self.record, constructed_local=False)])
        self.evidence = dict(reviewed=True, normal_official_client_receipt_confirmed=True,
            game_sha256='testimage', witness=dict(native_fields=self.record))

    def test_requires_receipt_review_and_offline_gate(self):
        e = copy.deepcopy(self.evidence);e['reviewed'] = False
        with self.assertRaises(ValueError):review(self.candidate,self.native,e)
        n = copy.deepcopy(self.native);n['offline']['online'] = 1
        with self.assertRaises(ValueError):review(self.candidate,n,self.evidence)

    def test_requires_unique_nonreplay_native_witness(self):
        n = copy.deepcopy(self.native);n['items'][0]['constructed_local'] = True
        with self.assertRaises(ValueError):review(self.candidate,n,self.evidence)
        c = copy.deepcopy(self.candidate);c['records'].append(self.record)
        with self.assertRaises(ValueError):review(c,self.native,self.evidence)

    def test_unknown_variant_is_preserved_and_quarantined(self):
        c = copy.deepcopy(self.candidate);c['records'].append(dict(self.record,map=0x3c2e2410))
        pack,quarantine,report = review(c,self.native,self.evidence)
        self.assertEqual(len(pack['messages']),1)
        self.assertEqual(quarantine[0]['map'],0x3c2e2410)
        self.assertEqual(report['quarantined'],1)
        self.assertFalse(report['full_world_coverage'])


if __name__ == '__main__':unittest.main()
