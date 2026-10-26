"""Local synthetic checks only; never acquires a ticket or contacts a server."""
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    tests=['protocol_pilot','rpc_frames','protocol_multi_target','finite_collection',
        'grouped_review','row_routing','campaign_collection','campaign_execution']
    results=[]
    for name in tests:
        process=subprocess.run([sys.executable,str(ROOT/'tests'/f'{name}.py')],capture_output=True,text=True)
        results.append(dict(test=name,passed=process.returncode==0,output=process.stdout+process.stderr))
    plan=ROOT/'build/research/canonical-campaign-plan-v8.json'
    approval=json.loads((ROOT/'evidence/canonical-campaign-authorization-v8.pending.json').read_text())
    spec=json.loads(plan.read_text());pack=json.loads((ROOT/'data/official-expansion-13069.json').read_text())
    manifest=json.loads((ROOT/'evidence/protocol-replay-dev3-build-manifest.json').read_text())
    source_ok=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in manifest['source_hashes'].items())
    ledger=json.loads((ROOT/'build/research/protocol-private/authorized-pilot-ledger.json').read_text())
    source_files=['tools/protocol_pilot/run_campaign.py','tools/protocol_pilot/campaign_budget.py',
        'tools/protocol_pilot/row_routing.py','tools/review_campaign_protocol.py',
        'tests/campaign_collection.py','tests/campaign_execution.py']
    report=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status='PREPARED_AWAITING_NEW_AUTHORIZATION',tests=results,all_tests_passed=all(r['passed'] for r in results),
        server_requests_sent_by_these_tests=0,plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
        approval_pending=approval['approved_by_user'] is False,
        targets=len(spec['targets']),groups=len(spec['groups']),
        preserved_session_attempts=ledger['session_attempts'],preserved_list_attempts=ledger['message_list_attempts'],
        existing_snapshot_records=len(pack['messages']),existing_snapshot_maps=len({r['map'] for r in pack['messages']}),
        runtime_source_matches_witnessed_dev3=source_ok,full_world_coverage=False,expanded_pack_gameplay_acceptance=False,
        implementation_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_files})
    path=ROOT/'evidence/canonical-campaign-readiness-v8.json'
    with path.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('tests','implementation_sha256')}))
    if not report['all_tests_passed'] or not source_ok:raise SystemExit(1)


if __name__=='__main__':main()
