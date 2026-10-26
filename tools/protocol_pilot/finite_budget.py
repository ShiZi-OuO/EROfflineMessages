"""One explicitly authorized immutable finite manifest, retaining all history."""
import hashlib
import json
import time
from pathlib import Path
from budget import PilotBudget


class FiniteBudget(PilotBudget):
    def __init__(self, path, authorization, manifest):
        approval = json.loads(Path(authorization).read_text(encoding='utf-8'))
        raw = Path(manifest).read_bytes()
        plan = json.loads(raw)
        count = len(plan['targets'])
        self.start_sessions=approval.get('baseline_session_attempts')
        self.start_lists=approval.get('baseline_list_attempts')
        if (approval.get('action') != 'ONE_FINITE_READONLY_MANIFEST'
                or approval.get('approved_by_user') is not True
                or approval.get('manifest_sha256') != hashlib.sha256(raw).hexdigest()
                or (self.start_sessions,self.start_lists) not in ((3,5),(4,70))
                or approval.get('total_session_attempt_limit') != self.start_sessions+1
                or approval.get('total_message_list_limit') != self.start_lists+count
                or approval.get('minimum_list_interval_seconds') != 10
                or not 1 <= count <= 1000 or plan['target_count'] != count):
            raise RuntimeError('Explicit finite manifest authorization required')
        self.limit = self.start_lists+count
        self.digest = approval['manifest_sha256']
        super().__init__(path)
        if (self.state['session_attempts'], self.state['message_list_attempts']) != (self.start_sessions,self.start_lists):
            raise RuntimeError('Exact preserved authorization history required; no reset or restart')

    def _reserve_locked(self, kind, now=None):
        now = time.time() if now is None else now
        if kind == 'session':
            if (self.state['session_attempts'], self.state['message_list_attempts']) != (self.start_sessions,self.start_lists):
                raise RuntimeError('Finite session already spent')
            self.state['session_attempts'] = self.start_sessions+1
            self.state['finite_manifest_sha256'] = self.digest
        elif kind == 'message_list':
            if self.state['session_attempts'] != self.start_sessions+1 or self.state.get('finite_manifest_sha256') != self.digest:
                raise RuntimeError('This finite session must be reserved first')
            if self.state['message_list_attempts'] >= self.limit:
                raise RuntimeError('Finite list limit exhausted')
            if now-self.state['last_list_time'] < 10:
                raise RuntimeError('Ten-second interval required')
            self.state['message_list_attempts'] += 1
            self.state['last_list_time'] = now
        else:
            raise ValueError('Only authentication and read-only lists authorized')
        self.state['events'].append(dict(kind=kind, utc_unix_seconds=now,
            reason='explicit finite manifest', manifest_sha256=self.digest))
        temp = self.path.with_suffix('.pending')
        temp.write_text(json.dumps(self.state,indent=2)+'\n')
        temp.replace(self.path)
