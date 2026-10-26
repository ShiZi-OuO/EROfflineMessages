"""Read only anonymous checkpoints; never read Steam's private library log."""
import argparse
import datetime
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',required=True);p.add_argument('--plan',required=True)
    p.add_argument('--output')
    a=p.parse_args();path=Path(a.checkpoint).resolve()
    if not path.is_relative_to(ROOT/'build/capture'):raise ValueError('Private semantic checkpoint required')
    data=json.loads(path.read_text());plan=json.loads(Path(a.plan).read_text())
    steps=[s for s in data['stages'] if isinstance(s,dict)]
    held=path.with_name(path.stem+'-quarantine.json')
    result=dict(queries_completed=len(steps),query_limit=plan.get('target_count',plan.get('maximum_list_queries')),
        saved_candidate_records=len(data['records']),map_ids_with_candidates=len({r['map'] for r in data['records']}),
        quarantined_candidates=len(json.loads(held.read_text())['records']) if held.exists() else 0,
        last_query=(steps[-1].get('target',steps[-1].get('query')) if steps else None),
        finished=data['finished'],finish_reason=data['finish_reason'],
        checkpoint_updated_utc=datetime.datetime.fromtimestamp(path.stat().st_mtime,datetime.timezone.utc).isoformat(),
        source='anonymous on-disk checkpoint; candidate counts are not individual gameplay acceptance',
        full_world_coverage=False)
    if a.output:
        output=Path(a.output).resolve()
        if output.parent!=ROOT/'evidence':raise ValueError('Sanitized progress output must be in evidence')
        pending=output.with_suffix('.pending');pending.write_text(json.dumps(result,indent=2)+'\n');pending.replace(output)
    print(json.dumps(result))


if __name__=='__main__':main()
