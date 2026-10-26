"""One separately authorized parent-area hypothesis collection; no reconnect."""
import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path
from budget import PilotBudget
from run_campaign import main


class ParentBudget(PilotBudget):
    def __init__(self,path,authorization,plan):
        a=json.loads(Path(authorization).read_text(encoding='utf-8'));raw=Path(plan).read_bytes();p=json.loads(raw)
        self.digest=hashlib.sha256(raw).hexdigest();self.limit=933
        if (a.get('action')!='ONE_PARENT_AREA_COLLECTION' or a.get('approved_by_user') is not True
                or a.get('plan_sha256')!=self.digest or a.get('baseline_session_attempts')!=8
                or a.get('baseline_list_attempts')!=911 or a.get('total_session_attempt_limit')!=9
                or a.get('total_message_list_limit')!=933 or a.get('minimum_list_interval_seconds')!=10
                or a.get('quarantine_unmapped_records') is not True
                or p.get('campaign_kind')!='parent_area_bounded_collection'
                or p.get('maximum_sessions')!=1 or p.get('maximum_list_queries')!=22
                or p.get('per_session_query_cap')!=22 or p.get('per_session_seconds')!=900
                or p.get('fallback_enabled') is not False or len(p.get('targets',[]))!=38
                or len(p.get('groups',[]))!=19):
            raise RuntimeError('Exact new 38-target/22-query parent-area authorization required')
        super().__init__(path)
        if (self.state['session_attempts'],self.state['message_list_attempts'])!=(8,911):
            raise RuntimeError('Preserved eight-session/911-list baseline required; no restart')

    def _reserve_locked(self,kind,now=None):
        now=time.time() if now is None else now
        if kind=='session':
            if self.state['session_attempts']!=8:raise RuntimeError('Parent-area session already spent')
            self.state.update(session_attempts=9,campaign_sha256=self.digest,campaign_segment_active=True,campaign_segment_normal=False)
        elif kind=='message_list':
            if (self.state.get('campaign_sha256')!=self.digest or self.state.get('campaign_segment_active') is not True
                    or self.state['session_attempts']!=9):raise RuntimeError('Active authorized parent-area session required')
            if self.state['message_list_attempts']>=self.limit:raise RuntimeError('22-list parent-area scope exhausted')
            if now-self.state['last_list_time']<10:raise RuntimeError('Ten-second interval required')
            self.state['message_list_attempts']+=1;self.state['last_list_time']=now
        elif kind in ('segment_normal_close','segment_failed_close'):
            if self.state.get('campaign_sha256')!=self.digest:raise RuntimeError('Wrong campaign close')
            self.state.update(campaign_segment_active=False,campaign_segment_normal=kind=='segment_normal_close')
        else:raise ValueError('RPC not authorized')
        self.state['events'].append(dict(kind=kind,utc_unix_seconds=now,campaign_sha256=self.digest))
        pending=self.path.with_suffix('.pending');pending.write_text(json.dumps(self.state,indent=2)+'\n');pending.replace(self.path)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('plan','authorization','steam-dll','game-exe','output','result'):p.add_argument('--'+flag,required=True)
    p.add_argument('--interface',required=True,type=int)
    asyncio.run(main(p.parse_args(),ParentBudget))
