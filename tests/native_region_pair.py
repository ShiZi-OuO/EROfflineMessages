import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_region_pair import native_pair


class NativePair(unittest.TestCase):
    def test_interior_does_not_use_payload_secondary_area(self):
        self.assertEqual(native_pair(3103001,0x1f030000),(3103001,3103001))
        self.assertEqual(native_pair(1105092,0x0b050000),(1105092,1105092))
    def test_open_world_uses_native_map_digits(self):
        self.assertEqual(native_pair(6100002,0x3c2a2500),(6042370,6100002))
        self.assertEqual(native_pair(6100004,0x3c2e2400),(6046360,6100004))
    def test_unknown_variant_and_bad_ids_rejected(self):
        for region, map_id in [(6100004,0x3c2e2410),(0,0x3c2e2400),(-1,1)]:
            with self.assertRaises(ValueError):native_pair(region,map_id)


if __name__ == '__main__':unittest.main()
