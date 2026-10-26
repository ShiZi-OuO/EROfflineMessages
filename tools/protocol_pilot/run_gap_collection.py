"""One newly authorized gap-recheck session. Never reconnects or adds targets."""
import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path
from budget import PilotBudget
from run_campaign import main, validate_plan


class GapBudget(PilotBudget):
    def __init__(self, path, authorization, plan):
        approval = json.loads(Path(authorization).read_text(encoding='utf-8'))
        raw = Path(plan).read_bytes()
        p = json.loads(raw)
        self.digest = hashlib.sha256(raw).hexdigest()
        validate_plan(p)
        if (approval.get('action') != 'ONE_GAP_RECHECK_COLLECTION'
                or approval.get('approved_by_user') is not True
                or approval.get('plan_sha256') != self.digest
                or approval.get('baseline_session_attempts') != 9
                or approval.get('baseline_list_attempts') != 933
                or approval.get('total_session_attempt_limit') != 10
                or approval.get('total_message_list_limit') != 1059
                or approval.get('minimum_list_interval_seconds') != 10
                or approval.get('quarantine_unmapped_records') is not True
                or p.get('campaign_kind') != 'single_target_gap_recheck'
                or p.get('maximum_sessions') != 1
                or p.get('maximum_list_queries') != 126
                or p.get('per_session_query_cap') != 126
                or p.get('per_session_seconds') != 1800
                or p.get('minimum_list_interval_seconds') != 10
                or p.get('fallback_enabled') is not False
                or len(p['targets']) != 123 or len(p['groups']) != 123
                or any(len(g['target_ids']) != 1 for g in p['groups'])):
            raise RuntimeError('New exact 123-target/126-query approval required')
        super().__init__(path)
        if (self.state['session_attempts'], self.state['message_list_attempts']) != (9, 933):
            raise RuntimeError('Preserved 9-session/933-list baseline required; no restart')

    def _reserve_locked(self, kind, now=None):
        now = time.time() if now is None else now
        if kind == 'session':
            if self.state['session_attempts'] != 9:
                raise RuntimeError('Gap-recheck authentication already spent')
            self.state.update(session_attempts=10, campaign_sha256=self.digest,
                              campaign_segment_active=True, campaign_segment_normal=False)
        elif kind == 'message_list':
            if (self.state.get('campaign_sha256') != self.digest
                    or self.state.get('campaign_segment_active') is not True
                    or self.state['session_attempts'] != 10):
                raise RuntimeError('Active authorized gap-recheck session required')
            if self.state['message_list_attempts'] >= 1059:
                raise RuntimeError('126-list gap-recheck scope exhausted')
            if now-self.state['last_list_time'] < 10:
                raise RuntimeError('Ten-second interval required')
            self.state['message_list_attempts'] += 1
            self.state['last_list_time'] = now
        elif kind in ('segment_normal_close', 'segment_failed_close'):
            if self.state.get('campaign_sha256') != self.digest:
                raise RuntimeError('Wrong campaign close')
            self.state.update(campaign_segment_active=False,
                              campaign_segment_normal=kind == 'segment_normal_close')
        else:
            raise ValueError('RPC not authorized')
        self.state['events'].append(dict(kind=kind, utc_unix_seconds=now,
                                        campaign_sha256=self.digest))
        pending = self.path.with_suffix('.pending')
        pending.write_text(json.dumps(self.state, indent=2)+'\n', encoding='utf-8')
        pending.replace(self.path)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('plan', 'authorization', 'steam-dll', 'game-exe', 'output', 'result'):
        p.add_argument('--'+flag, required=True)
    p.add_argument('--interface', required=True, type=int)
    asyncio.run(main(p.parse_args(), GapBudget))
