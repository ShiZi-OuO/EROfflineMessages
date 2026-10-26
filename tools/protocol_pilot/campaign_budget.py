"""Prepared two-segment finite scope. Refusals never permit a next segment."""
import hashlib
import json
import time
from pathlib import Path
from budget import PilotBudget


class CampaignBudget(PilotBudget):
    def __init__(self,path,authorization,plan):
        approval=json.loads(Path(authorization).read_text(encoding='utf-8'));raw=Path(plan).read_bytes();spec=json.loads(raw)
        self.digest=hashlib.sha256(raw).hexdigest()
        if (approval.get('action')!='TWO_SEGMENT_CANONICAL_COLLECTION'
                or approval.get('approved_by_user') is not True
                or approval.get('plan_sha256')!=self.digest
                or approval.get('baseline_session_attempts')!=6
                or approval.get('baseline_list_attempts')!=479
                or approval.get('total_session_attempt_limit')!=8
                or approval.get('total_message_list_limit')!=979
                or approval.get('minimum_list_interval_seconds')!=10
                or approval.get('normal_segment_transition_only') is not True
                or approval.get('quarantine_unmapped_records') is not True
                or spec.get('maximum_sessions')!=2
                or spec.get('maximum_list_queries')!=500
                or spec.get('per_session_query_cap')!=250
                or spec.get('per_session_seconds')!=2700):
            raise RuntimeError('New explicit two-segment canonical collection authorization required')
        super().__init__(path)
        if (self.state['session_attempts'],self.state['message_list_attempts'])!=(6,479):
            raise RuntimeError('Preserved six-session/479-list history required; no reset/restart')
    def _reserve_locked(self,kind,now=None):
        now=time.time() if now is None else now
        if kind=='session':
            count=self.state['session_attempts']
            if count not in (6,7):raise RuntimeError('Campaign session scope exhausted')
            if count==7 and (self.state.get('campaign_sha256')!=self.digest or self.state.get('campaign_segment_normal') is not True):
                raise RuntimeError('Next segment forbidden after any failure')
            self.state['session_attempts']=count+1;self.state['campaign_sha256']=self.digest
            self.state['campaign_segment_normal']=False;self.state['campaign_segment_lists']=0
            self.state['campaign_segment_active']=True
        elif kind=='message_list':
            if (self.state.get('campaign_sha256')!=self.digest or self.state['session_attempts'] not in (7,8)
                    or self.state.get('campaign_segment_active') is not True):
                raise RuntimeError('Campaign session reservation required')
            if self.state['message_list_attempts']>=979 or self.state['campaign_segment_lists']>=250:
                raise RuntimeError('Explicit total/segment request cap exhausted')
            if now-self.state['last_list_time']<10:raise RuntimeError('Ten-second list interval required')
            self.state['message_list_attempts']+=1;self.state['last_list_time']=now;self.state['campaign_segment_lists']+=1
        elif kind in ('segment_normal_close','segment_failed_close'):
            if self.state.get('campaign_sha256')!=self.digest:raise RuntimeError('Wrong campaign close')
            self.state['campaign_segment_normal']=kind=='segment_normal_close'
            self.state['campaign_segment_active']=False
        else:raise ValueError('No other RPC or bookkeeping action authorized')
        self.state['events'].append(dict(kind=kind,utc_unix_seconds=now,campaign_sha256=self.digest))
        pending=self.path.with_suffix('.pending');pending.write_text(json.dumps(self.state,indent=2)+'\n');pending.replace(self.path)
