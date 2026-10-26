import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from coverage_gap_audit import nearest, point


class GapDistances(unittest.TestCase):
    def test_neighboring_tiles_compare_in_world_coordinates(self):
        rows = [dict(id='test', map=0x3c292400, position=[127., 10., 0.])]
        result = nearest(0x3c2a2400, [-127., 10., 0.], rows)
        self.assertEqual(result['distance_metres'], 2.)
        self.assertFalse(result['same_default_map'])
        self.assertFalse(result['runtime_visibility_verified'])

    def test_indoor_and_dlc_domains_are_not_mixed(self):
        rows = [dict(id='indoor', map=0x0c070000, position=[0., 0., 0.]),
                dict(id='dlc', map=0x3d2a2400, position=[0., 0., 0.])]
        self.assertIsNone(nearest(0x0c060000, [0., 0., 0.], rows))
        self.assertIsNone(nearest(0x3c2a2400, [0., 0., 0.], rows))

    def test_variants_and_invalid_points_fail_instead_of_normalizing(self):
        for map_id, pos in [(0x3c2a2410, [0., 0., 0.]),
                            (0x3c2a2400, [float('nan'), 0., 0.])]:
            with self.assertRaises(ValueError): point(map_id, pos)

    def test_distance_includes_height(self):
        result = nearest(0x0c060000, [0., 0., 0.],
                         [dict(id='a', map=0x0c060000, position=[0., 100., 0.])])
        self.assertEqual(result['distance_metres'], 100.)


if __name__ == '__main__': unittest.main()
