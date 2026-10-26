"""Explicit additional small validation; preserves the two-session/two-list history."""
import json
import time
from pathlib import Path
from budget import PilotBudget

class RoutedBudget(PilotBudget):
    def __init__(self,path,authorization):
        approval=json.loads(Path(authorization).read_text(encoding='utf-8'))
        if (approval.get('action')!='ONE_ROUTED_READONLY_VALIDATION'
                or approval.get('approved_by_user') is not True
                or approval.get('total_session_attempt_limit')!=3
                or approval.get('total_message_list_limit')!=5
                or approval.get('minimum_list_interval_seconds')!=10):
            raise RuntimeError('New explicit routed validation authorization required')
        super().__init__(path)
        if (self.state['session_attempts'],self.state['message_list_attempts'])!=(2,2):
            raise RuntimeError('Requires preserved two-session/two-list history; no reset')
    def _reserve_locked(self,kind,now=None):
        now=time.time() if now is None else now
        if kind=='session':
            if self.state['session_attempts']!=2:raise RuntimeError('Routed validation session already spent')
            self.state['session_attempts']=3
        elif kind=='message_list':
            if self.state['message_list_attempts']>=5:raise RuntimeError('Five total list requests exhausted')
            if now-self.state['last_list_time']<10:raise RuntimeError('Ten-second list interval required')
            self.state['message_list_attempts']+=1;self.state['last_list_time']=now
        else:raise ValueError('RPC not authorized by this validation')
        self.state['events'].append(dict(kind=kind,utc_unix_seconds=now,reason='explicit routed read-only validation'))
        temp=self.path.with_suffix('.pending');temp.write_text(json.dumps(self.state,indent=2)+'\n');temp.replace(self.path)
