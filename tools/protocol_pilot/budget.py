"""Persistent small-pilot limits. Reservation happens before sending, no auto retry."""
import json
import os
import time
from pathlib import Path


class PilotBudget:
    def __init__(self,path):
        self.path=Path(path)
        self.state=json.loads(self.path.read_text()) if self.path.exists() else dict(
            schema_version=1,authorization='user approved one limited independent protocol pilot',
            session_attempts=0,message_list_attempts=0,last_list_time=0,events=[])
    def reserve(self,kind,now=None):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        lock=self.path.with_suffix('.lock')
        descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        try:
            if self.path.exists():self.state=json.loads(self.path.read_text())
            return self._reserve_locked(kind,now)
        finally:
            os.close(descriptor);lock.unlink()
    def _reserve_locked(self,kind,now=None):
        now=time.time() if now is None else now
        if kind=='session':
            if self.state['session_attempts']>=1:raise RuntimeError('Pilot session attempt already spent')
            self.state['session_attempts']+=1
        elif kind=='message_list':
            if self.state['message_list_attempts']>=3:raise RuntimeError('Three-request pilot budget exhausted')
            if self.state['message_list_attempts'] and now-self.state['last_list_time']<10:
                raise RuntimeError('Pilot requires at least ten seconds between list requests')
            self.state['message_list_attempts']+=1;self.state['last_list_time']=now
        else:raise ValueError('RPC not authorized by this pilot')
        self.state['events'].append(dict(kind=kind,utc_unix_seconds=now))
        temp=self.path.with_suffix('.pending');temp.write_text(json.dumps(self.state,indent=2)+'\n');temp.replace(self.path)
