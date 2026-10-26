import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/protocol_pilot'))
from run_gap_collection import GapBudget


class GapScope(unittest.TestCase):
    def fixture(self, root):
        plan = ROOT/'build/research/gap-recheck-plan-v10.json'
        approval = json.loads((ROOT/'evidence/gap-recheck-authorization-v10.pending.json').read_text())
        approval_path = root/'approval.json'
        ledger = root/'ledger.json'
        ledger.write_text(json.dumps(dict(session_attempts=9, message_list_attempts=933,
                                         last_list_time=0, events=[])))
        return plan, approval, approval_path, ledger

    def test_pending_approval_and_altered_plan_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan, a, approval, ledger = self.fixture(root)
            approval.write_text(json.dumps(a))
            with self.assertRaises(RuntimeError): GapBudget(ledger, approval, plan)
            a['approved_by_user'] = True
            approval.write_text(json.dumps(a))
            changed = root/'changed.json'
            changed.write_bytes(plan.read_bytes()+b'\n')
            with self.assertRaises(RuntimeError): GapBudget(ledger, approval, changed)

    def test_rate_cap_and_reconnect_are_refused(self):
        for failed in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                plan, a, approval, ledger = self.fixture(root)
                a['approved_by_user'] = True
                approval.write_text(json.dumps(a))
                budget = GapBudget(ledger, approval, plan)
                budget.reserve('session', 1)
                for i in range(126): budget.reserve('message_list', 10+i*10)
                with self.assertRaises(RuntimeError): budget.reserve('message_list', 1270)
                budget.reserve('segment_failed_close' if failed else 'segment_normal_close', 1280)
                with self.assertRaises(RuntimeError): budget.reserve('session', 1290)
                with self.assertRaises(RuntimeError): GapBudget(ledger, approval, plan)
                self.assertEqual(budget.state['message_list_attempts'], 1059)

    def test_rate_limit_prevents_early_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan, a, approval, ledger = self.fixture(root)
            a['approved_by_user'] = True
            approval.write_text(json.dumps(a))
            budget = GapBudget(ledger, approval, plan)
            budget.reserve('session', 1)
            budget.reserve('message_list', 10)
            with self.assertRaises(RuntimeError): budget.reserve('message_list', 19)
            self.assertEqual(budget.state['message_list_attempts'], 934)


if __name__ == '__main__': unittest.main()
