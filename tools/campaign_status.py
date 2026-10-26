"""Sanitized v8 disk status; no game, ticket, private library log or network access."""
import datetime
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
load=lambda p:json.loads(p.read_text(encoding='utf-8'))


def main():
    path=ROOT/'build/capture/protocol-canonical-candidates-v8.json'
    data=load(path);base=load(ROOT/'data/official-expansion-13069.json')
    q=load(path.with_name(path.stem+'-quarantine.json'))
    a={r['map'] for r in base['messages']};b={r['map'] for r in data['records']}
    stages=data['stages'];ledger=load(ROOT/'build/research/protocol-private/authorized-pilot-ledger.json')
    status=dict(queries_completed=len(stages),list_limit=500,records=len(data['records']),
        quarantined=len(q['records']),candidate_new_map_ids=len(b-a),candidate_union_map_ids=len(a|b),
        cumulative_session_attempts=ledger['session_attempts'],cumulative_list_attempts=ledger['message_list_attempts'],
        last_query=stages[-1]['query'] if stages else None,finished=data['finished'],
        updated_utc=datetime.datetime.fromtimestamp(path.stat().st_mtime,datetime.timezone.utc).isoformat(),
        not_individual_gameplay_acceptance=True,full_world_coverage=False)
    receipt=ROOT/'evidence/protocol-canonical-result-v8.json'
    if receipt.exists():
        r=load(receipt)
        status.update(error=r.get('error'),bounded_stop_reason=r.get('bounded_stop_reason'),
            groups_completed=r['groups_completed'],groups_total=r['groups_total'])
    output=ROOT/'evidence/protocol-canonical-live-progress-v8.json';pending=output.with_suffix('.pending')
    pending.write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8');pending.replace(output)
    print(json.dumps(status))


if __name__=='__main__':main()
