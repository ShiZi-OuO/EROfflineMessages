"""Provenance comparison tests. Never opens a game or network connection."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from capture_client_cache import anonymous_records, compare


def item(**updates):
    result = dict(constructed_local=False, map=0x1f030000, area=3103001,
        secondary_area=0, position=[1., 2., 3.], yaw=0., template1=10000,
        word1=32032, conjunction=0, template2=0, word2=0, good=10, poor=1)
    result.update(updates)
    return result


class CacheComparison(unittest.TestCase):
    def test_constructed_never_becomes_candidate(self):
        self.assertEqual(compare(dict(items=[]), dict(items=[item(constructed_local=True)])), [])

    def test_rating_change_alone_is_not_new_receipt(self):
        self.assertEqual(compare(dict(items=[item()]), dict(items=[item(good=99)])), [])

    def test_new_semantics_are_candidates_not_identity_exports(self):
        record = item(position=[2., 2., 3.], player_name='must not export',
                      account_id='must not export', flags=8, ttl=300.)
        result = compare(dict(items=[item()]), dict(items=[record]))
        self.assertEqual(len(result), 1)
        self.assertFalse({'player_name', 'account_id', 'flags', 'ttl'} & result[0].keys())
        self.assertEqual(len(result[0]['candidate_key']), 64)

    def test_duplicate_semantics_and_bad_vectors(self):
        record = item()
        self.assertEqual(len(anonymous_records(dict(items=[record, copy.deepcopy(record)]))), 1)
        with self.assertRaises(ValueError):
            anonymous_records(dict(items=[item(position=[float('nan'), 0., 0.])]))


if __name__ == '__main__':
    unittest.main()
