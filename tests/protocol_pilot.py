"""Wire/limit tests use fake bytes only; never generate tickets or connect."""
import struct
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/protocol_pilot'))
from budget import PilotBudget
from wire import create_session,message_list,response_header


class PilotTests(unittest.TestCase):
    def test_session_native_mixed_width_layout(self):
        b=create_session(1,[11,22,33],0x1122334455667788,b'FAKE',platform=2,
                         region=3,language=4,cross_region=True,flags=True,tail=(5,6,7,8))
        expected=(struct.pack('<BII3IQI',4,1,0,11,22,33,0x1122334455667788,1)
                  +struct.pack('<I',4)+b'FAKE'+struct.pack('<IBIIBI4I',2,1,3,4,1,0,5,6,7,8))
        self.assertEqual(b,expected)
    def test_only_query_shape_and_malformed_response_rejected(self):
        self.assertEqual(message_list(2,[(31030,3103001)]),
            struct.pack('<BIIIIII',4,2,18,1,31030,3103001,0))
        with self.assertRaises(ValueError):message_list(2,[(1,2),(1,2)])
        with self.assertRaises(ValueError):response_header(b'\x05',1,0)
        with self.assertRaises(RuntimeError):response_header(struct.pack('<BIBI',5,1,0,100),1,0)
    def test_persistent_request_and_rate_limits(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger.json';b=PilotBudget(p);b.reserve('session',1)
            with self.assertRaises(RuntimeError):PilotBudget(p).reserve('session',2)
            b.reserve('message_list',100)
            with self.assertRaises(RuntimeError):b.reserve('message_list',109)
            b.reserve('message_list',110);PilotBudget(p).reserve('message_list',120)
            with self.assertRaises(RuntimeError):b.reserve('message_list',130)
            with self.assertRaises(RuntimeError):PilotBudget(p).reserve('message_list',130)
            with self.assertRaises(ValueError):b.reserve('evaluate',150)

    def test_response_identity_and_raw_payload_never_exported(self):
        from run_pilot import message_response
        raw=bytearray(520);struct.pack_into('<II',raw,0,10,512)
        raw[8:8+16]=b'PRIVATE-IDENTITY'
        struct.pack_into('<II3ff8H',raw,8+0x1c0,0x1f030000,31030,
                         1.,2.,3.,0.,10000,255,30008,0,0,0,0,0)
        data=(struct.pack('<BIBII',5,2,1,18,1)+struct.pack('<iiqiiI',123456,789012,999888,4,3,len(raw))
              +raw+struct.pack('<III',31030,3103001,1)+struct.pack('<I',6)+b'SECRET')
        rows,summary=message_response(bytes(data),2,0x1f030000)
        self.assertEqual(summary['unexpected_map_counts'],{})
        self.assertEqual(rows[0]['good']+rows[0]['poor'],7)
        self.assertNotIn('PRIVATE',str(rows));self.assertNotIn('SECRET',str(rows))
        self.assertNotIn('player_id',rows[0]);self.assertNotIn('identifier',rows[0])
        _,wrong=message_response(bytes(data),2,0x1f030000,expected_pair=(99,88))
        self.assertTrue(wrong['unexpected_pair_counts'])

    def test_corrected_extension_keeps_history_and_list_cap(self):
        from corrected_budget import CorrectedBudget
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ledger.json';approval=Path(d)/'approval.json'
            old=PilotBudget(path);old.reserve('session',1);old.reserve('message_list',100)
            approval.write_text(json.dumps(dict(action='ONE_CORRECTED_INDEPENDENT_PROTOCOL_ATTEMPT',
                approved_by_user=True,total_session_attempt_limit=2,total_message_list_limit=3,minimum_list_interval_seconds=10)))
            first=CorrectedBudget(path,approval);stale=CorrectedBudget(path,approval)
            first.reserve('session',101)
            with self.assertRaises(RuntimeError):stale.reserve('session',102)
            first.reserve('message_list',110);first.reserve('message_list',120)
            with self.assertRaises(RuntimeError):first.reserve('message_list',130)
            state=json.loads(path.read_text())
            self.assertEqual(state['session_attempts'],2);self.assertEqual(state['message_list_attempts'],3)
            self.assertEqual(state['events'][0]['utc_unix_seconds'],1)

    def test_pending_extension_does_not_change_ledger(self):
        from corrected_budget import CorrectedBudget
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ledger.json';approval=Path(d)/'approval.json'
            PilotBudget(path).reserve('session',1);before=path.read_bytes()
            approval.write_text(json.dumps(dict(approved_by_user=False)))
            with self.assertRaises(RuntimeError):CorrectedBudget(path,approval)
            self.assertEqual(before,path.read_bytes())

    def test_routed_budget_keeps_spent_requests_and_stops_at_new_cap(self):
        from routed_budget import RoutedBudget
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ledger.json';approval=Path(d)/'approval.json'
            path.write_text(json.dumps(dict(schema_version=1,session_attempts=2,message_list_attempts=2,
                last_list_time=100,events=[{'kind':'prior_history'}])))
            approval.write_text(json.dumps(dict(action='ONE_ROUTED_READONLY_VALIDATION',approved_by_user=True,
                total_session_attempt_limit=3,total_message_list_limit=5,minimum_list_interval_seconds=10)))
            b=RoutedBudget(path,approval);stale=RoutedBudget(path,approval);b.reserve('session',101)
            with self.assertRaises(RuntimeError):stale.reserve('session',102)
            with self.assertRaises(RuntimeError):b.reserve('message_list',109)
            for t in [110,120,130]:b.reserve('message_list',t)
            with self.assertRaises(RuntimeError):b.reserve('message_list',140)
            s=json.loads(path.read_text());self.assertEqual(s['session_attempts'],3)
            self.assertEqual(s['message_list_attempts'],5);self.assertEqual(s['events'][0],{'kind':'prior_history'})

    def test_routed_pending_approval_is_not_authorization(self):
        from routed_budget import RoutedBudget
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ledger.json';approval=Path(d)/'approval.json'
            path.write_text(json.dumps(dict(session_attempts=2,message_list_attempts=2)))
            before=path.read_bytes();approval.write_text(json.dumps(dict(approved_by_user=False)))
            with self.assertRaises(RuntimeError):RoutedBudget(path,approval)
            self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
