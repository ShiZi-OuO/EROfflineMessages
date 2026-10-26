import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/protocol_pilot'))
from row_routing import split_rows


class RowTests(unittest.TestCase):
    def test_keep_valid_rows_quarantine_variant_without_rewriting(self):
        records=[dict(map=0x3c2c2500,candidate_key='a'),dict(map=0x3c2c2510,candidate_key='b')]
        original=copy.deepcopy(records)
        routes=[dict(candidate_key=k,pair=[6044370,6100001]) for k in ('a','b')]
        a,q=split_rows(records,routes,{(6044370,6100001):{0x3c2c2500}})
        self.assertEqual(a,[records[0]]);self.assertEqual(q,[records[1]])
        self.assertEqual(records,original)
    def test_wrong_region_grid_or_lod_is_not_silently_admitted(self):
        for map_id in (0x3c2c2610,0x3c2c2502,0x3c2c2520,0xffffffff):
            with self.assertRaises(ValueError):split_rows([dict(map=map_id,candidate_key='a')],
                [dict(candidate_key='a',pair=[6044370,6100001])],{(6044370,6100001):{0x3c2c2500}})
        with self.assertRaises(ValueError):split_rows([dict(map=0x3c2c2500,candidate_key='a')],
            [dict(candidate_key='a',pair=[1,2])],{(6044370,6100001):{0x3c2c2500}})


if __name__=='__main__':unittest.main()
