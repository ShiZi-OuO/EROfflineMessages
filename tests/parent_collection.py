import json
import tempfile
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/protocol_pilot'))
from run_parent_collection import ParentBudget
from run_campaign import validate_plan


class ParentTests(unittest.TestCase):
    def test_new_scope_requires_approval_and_never_reconnects(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ledger=root/'ledger.json';plan=root/'plan.json';approval=root/'approval.json'
            plan.write_bytes((ROOT/'build/research/parent-area-query-plan-v9.json').read_bytes())
            a=json.loads((ROOT/'evidence/parent-area-authorization-v9.pending.json').read_text())
            approval.write_text(json.dumps(a));ledger.write_text(json.dumps(dict(session_attempts=8,message_list_attempts=911,last_list_time=0,events=[])))
            with self.assertRaises(RuntimeError):ParentBudget(ledger,approval,plan)
            a['approved_by_user']=True;approval.write_text(json.dumps(a));b=ParentBudget(ledger,approval,plan)
            b.reserve('session',1)
            for i in range(22):b.reserve('message_list',10+i*10)
            with self.assertRaises(RuntimeError):b.reserve('message_list',240)
            b.reserve('segment_normal_close',250)
            with self.assertRaises(RuntimeError):b.reserve('session',260)
            with self.assertRaises(RuntimeError):ParentBudget(ledger,approval,plan)
            self.assertEqual((b.state['session_attempts'],b.state['message_list_attempts']),(9,933))

    def test_exact_plan_contains_known_grace_gap_maps(self):
        p=json.loads((ROOT/'build/research/parent-area-query-plan-v9.json').read_text())
        self.assertEqual(len(validate_plan(p)),41)
        maps={m for t in p['targets'] for m in t['expected_maps']}
        for m in (0x3c342600,0x3c353400,0x3c363500):self.assertIn(m,maps)
        self.assertFalse(p['fallback_enabled'])


if __name__=='__main__':unittest.main()
