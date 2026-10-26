"""Prepared grouped collection scope. No implicit extension of single queries."""
import hashlib
import json
import time
from pathlib import Path
from budget import PilotBudget


class GroupBudget(PilotBudget):
    def __init__(self,path,authorization,plan):
        approval=json.loads(Path(authorization).read_text())
        raw=Path(plan).read_bytes();spec=json.loads(raw)
        self.initial_sessions=approval.get('baseline_session_attempts')
        self.initial_lists=approval.get('baseline_list_attempts')
        maximum=spec['maximum_list_queries']
        self.digest=hashlib.sha256(raw).hexdigest()
        recovery=approval.get('action')=='ONE_GROUPED_RECOVERY_COLLECTION'
        valid_action=(approval.get('action')=='ONE_GROUPED_WORLD_COLLECTION' or recovery)
        if (not valid_action
                or approval.get('approved_by_user') is not True
                or approval.get('plan_sha256')!=self.digest
                or self.initial_sessions!=5 or type(self.initial_lists) is not int
                or not 70<=self.initial_lists<=691
                or approval.get('total_session_attempt_limit')!=6
                or approval.get('total_message_list_limit')!=self.initial_lists+maximum
                or approval.get('minimum_list_interval_seconds')!=10
                or not 1<=maximum<=1000
                or approval.get('one_single_fallback_per_missing_target') is not True):
            raise RuntimeError('New explicit grouped-world authorization required')
        if recovery and (self.initial_lists!=430 or maximum!=300
                or spec.get('maximum_session_seconds')!=3000
                or approval.get('acknowledged_prior_rpc_error')!=20000):
            raise RuntimeError('Explicit post-error 300-request/50-minute scope required')
        self.limit=self.initial_lists+maximum
        super().__init__(path)
        if (self.state['session_attempts'],self.state['message_list_attempts'])!=(self.initial_sessions,self.initial_lists):
            raise RuntimeError('Exact current history required; no reset/restart')

    def _reserve_locked(self,kind,now=None):
        now=time.time() if now is None else now
        if kind=='session':
            if (self.state['session_attempts'],self.state['message_list_attempts'])!=(self.initial_sessions,self.initial_lists):
                raise RuntimeError('Grouped session scope spent')
            self.state['session_attempts']=6;self.state['group_plan_sha256']=self.digest
        elif kind=='message_list':
            if self.state['session_attempts']!=6 or self.state.get('group_plan_sha256')!=self.digest:
                raise RuntimeError('Grouped session reservation required')
            if self.state['message_list_attempts']>=self.limit:raise RuntimeError('Grouped request scope exhausted')
            if now-self.state['last_list_time']<10:raise RuntimeError('Ten-second list interval required')
            self.state['message_list_attempts']+=1;self.state['last_list_time']=now
        else:raise ValueError('Only authentication and readonly lists permitted')
        self.state['events'].append(dict(kind=kind,utc_unix_seconds=now,reason='explicit grouped world plan',plan_sha256=self.digest))
        pending=self.path.with_suffix('.pending');pending.write_text(json.dumps(self.state,indent=2)+'\n');pending.replace(self.path)
