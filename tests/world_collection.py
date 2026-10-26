"""Meaningful data-integrity tests for multi-session collection; no process access."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from merge_official_packs import merge
from world_coverage import inventory


def pack():
    return dict(schema_version=1, game='eldenring', source_type='official_client_sample',
        messages=[dict(id='7d00000000000001', map=0x1f030000, area=3103001,
            secondary_area=31030, position=[1., 2., 3.], yaw=0., template1=10000,
            word1=30008, conjunction=0, template2=0, word2=0, good=4, poor=3)])


class Collection(unittest.TestCase):
    def test_repeat_sample_updates_rating_without_duplicate(self):
        a=pack(); b=copy.deepcopy(a); b['messages'][0].update(good=9, id='7d00000000000002')
        result=merge([a,b]); self.assertEqual(len(result['messages']),1)
        self.assertEqual(result['messages'][0]['good'],9)

    def test_rejects_identity_and_unreviewed_candidates(self):
        a=pack(); a['messages'][0]['player_id']=123
        with self.assertRaises(ValueError): merge([a])
        for kind in ['constructed','unverified_client_cache_candidates']:
            a=pack();a['source_type']=kind
            with self.assertRaises(ValueError):merge([a])

    def test_inventory_does_not_equate_samples_with_coverage(self):
        params={'parameters':{'PlayRegionParam':{'rows':[
            {'id':3103001,'fields':{'enableBloodMessage':1}},
            {'id':999,'fields':{'enableBloodMessage':1}}]}}}
        maps={'maps':[{'path':'map/m31_03_00_00.msb.dcx','archive':'Data2',
                      'collision_play_regions':[3103001]}]}
        result=inventory(params,maps,[pack(),pack()])
        self.assertEqual(result['unique_received_samples'],1)
        self.assertEqual(result['parameter_rows_with_samples'],1)
        self.assertFalse(result['full_world_coverage'])
        self.assertFalse(result['regions'][0]['whole_region_coverage_verified'])


if __name__=='__main__':unittest.main()
