"""Synthetic bytes only. Group-query support is not a server-tested feature."""
import struct
import hashlib
import json
import tempfile
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/protocol_pilot'))
from run_pilot import message_response
from plan_group_queries import build
from group_budget import GroupBudget
from run_pilot import session_response
import time


def entry(map_id, pair):
    raw=bytearray(520);struct.pack_into('<II',raw,0,10,512)
    struct.pack_into('<II3ff8H',raw,8+0x1c0,map_id,31030,1.,2.,3.,0.,10000,255,30008,0,0,0,0,0)
    struct.pack_into('<I',raw,8+0x1f8,pair[1])
    return struct.pack('<iiqiiI',123456,789012,999888,4,3,len(raw))+raw+struct.pack('<III',*pair,0)


class MultiTests(unittest.TestCase):
    def test_session_summary_keeps_only_relative_lifetime(self):
        now=int(time.time())
        def blob(b):return struct.pack('<I',len(b))+b
        frame=struct.pack('<BIBIi',5,1,1,0,123456)+blob(b'PRIVATE-ID')+blob(b'PRIVATE-IP')
        frame+=struct.pack('<qqq',999888,now,now+3600)+blob(b'PRIVATE-COOKIE')+blob(b'')
        summary=session_response(frame)
        self.assertTrue(summary['lifetime_metadata_available']);self.assertEqual(summary['lifetime_seconds'],3600)
        self.assertNotIn('PRIVATE',str(summary));self.assertNotIn(str(now),str(summary));self.assertNotIn('999888',str(summary))
    def test_group_scope_requires_new_approval_and_never_reopens(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ledger=root/'ledger.json';plan=root/'plan.json';auth=root/'approval.json'
            plan.write_text(json.dumps(dict(maximum_list_queries=2)))
            ledger.write_text(json.dumps(dict(session_attempts=5,message_list_attempts=691,last_list_time=100,events=[])))
            a=dict(action='ONE_GROUPED_WORLD_COLLECTION',approved_by_user=False,
                plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),baseline_session_attempts=5,
                baseline_list_attempts=691,total_session_attempt_limit=6,total_message_list_limit=693,
                minimum_list_interval_seconds=10,one_single_fallback_per_missing_target=True)
            auth.write_text(json.dumps(a))
            with self.assertRaises(RuntimeError):GroupBudget(ledger,auth,plan)
            a['approved_by_user']=True;auth.write_text(json.dumps(a))
            first=GroupBudget(ledger,auth,plan);stale=GroupBudget(ledger,auth,plan)
            first.reserve('session',101)
            with self.assertRaises(RuntimeError):stale.reserve('session',102)
            first.reserve('message_list',110)
            with self.assertRaises(RuntimeError):first.reserve('message_list',119)
            first.reserve('message_list',120)
            with self.assertRaises(RuntimeError):first.reserve('message_list',130)
            with self.assertRaises(RuntimeError):GroupBudget(ledger,auth,plan)

    def test_group_plan_has_no_duplicate_targets_and_bounded_fallbacks(self):
        control=[dict(id=str(n),pair=pair,expected_maps=[n]) for n,pair in enumerate([[3103001,3103001],[6042370,6100002],[3002001,3002001]])]
        new=[dict(id='new'+str(n),pair=[6000000+n,6100000],expected_maps=[n]) for n in range(17)]
        plan=build(dict(targets=control),dict(targets=control+new))
        self.assertEqual([len(g['target_ids']) for g in plan['groups']],[8,8,1])
        self.assertEqual(plan['maximum_list_queries'],24)
        self.assertFalse(plan['server_group_queries_tested'])
        ids=[i for g in plan['groups'] for i in g['target_ids']]
        self.assertEqual(len(ids),len(set(ids)))

    def test_each_pair_checks_its_own_map_not_the_global_union(self):
        route={(3103001,3103001):{0x1f030000},(3002001,3002001):{0x1e020000}}
        frame=struct.pack('<BIBII',5,2,1,18,2)+entry(0x1f030000,(3103001,3103001))+entry(0x1e020000,(3002001,3002001))
        rows,s=message_response(frame,2,None,expected_targets=route)
        self.assertEqual(len(rows),2);self.assertFalse(s['unexpected_map_counts']);self.assertFalse(s['unexpected_pair_counts'])
        self.assertEqual(s['entries_per_pair'],{'3103001:3103001':1,'3002001:3002001':1})
        wrong=struct.pack('<BIBII',5,2,1,18,1)+entry(0x1f030000,(3002001,3002001))
        _,s=message_response(wrong,2,None,expected_targets=route)
        self.assertTrue(s['unexpected_map_counts'])
        self.assertFalse(s['unexpected_pair_counts'])

    def test_unknown_pair_is_rejected_in_metadata_and_privacy_preserved(self):
        frame=struct.pack('<BIBII',5,2,1,18,1)+entry(0x1f030000,(1,2))
        rows,s=message_response(frame,2,None,expected_targets={(3103001,3103001):{0x1f030000}})
        self.assertEqual(s['unexpected_pair_counts'],{'1:2':1})
        self.assertNotIn('123456',str(rows));self.assertNotIn('player',str(rows))
        with self.assertRaises(ValueError):message_response(frame,2,None,expected_targets={})


if __name__=='__main__':unittest.main()
