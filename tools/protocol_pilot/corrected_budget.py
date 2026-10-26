"""One explicit additional corrected session; preserves all previous counters."""
import json
import time
from pathlib import Path
from budget import PilotBudget


class CorrectedBudget(PilotBudget):
    def __init__(self,path,authorization):
        approval=json.loads(Path(authorization).read_text(encoding='utf-8'))
        if (approval.get('action')!='ONE_CORRECTED_INDEPENDENT_PROTOCOL_ATTEMPT'
                or approval.get('approved_by_user') is not True
                or approval.get('total_session_attempt_limit')!=2
                or approval.get('total_message_list_limit')!=3
                or approval.get('minimum_list_interval_seconds')!=10):
            raise RuntimeError('New explicit correction authorization required; no requests made')
        super().__init__(path)
        if self.state['session_attempts']!=1:
            raise RuntimeError('Requires exactly the one previous session attempt; no reset or third attempt')

    def _reserve_locked(self,kind,now=None):
        if kind!='session':return super()._reserve_locked(kind,now)
        if self.state['session_attempts']!=1:
            raise RuntimeError('Corrected session attempt already spent or history inconsistent')
        now=time.time() if now is None else now
        self.state['session_attempts']=2
        self.state['events'].append(dict(kind='session',utc_unix_seconds=now,
            reason='one explicitly approved static-version correction',total_attempts=2))
        temp=self.path.with_suffix('.pending')
        temp.write_text(json.dumps(self.state,indent=2)+'\n');temp.replace(self.path)
