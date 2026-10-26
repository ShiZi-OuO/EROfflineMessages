"""Bounded offline VM_READ expiry evidence; no TTL writes or server access."""
import argparse
import collections
import datetime
import json
import time
from pathlib import Path
from observe import Reader


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--map',required=True,type=lambda x:int(x,0));p.add_argument('--pause-file',required=True)
    p.add_argument('--output',required=True);p.add_argument('--seconds',type=int,default=380)
    a=p.parse_args()
    if not 1<=a.seconds<=420:raise ValueError('Expiry observation bound')
    output=Path(a.output);flag=Path(a.pause_file)
    if output.exists():raise ValueError('Fresh expiry evidence required')
    reader=Reader();started=time.monotonic()
    report=dict(type='offline_native_cache_expiry',target_map=a.map,observations=[],
        natural_clear_observed=False,ttl_or_memory_modified=False,server_requests=0,finished=False)
    try:
        while time.monotonic()-started<=a.seconds:
            if not flag.exists():raise RuntimeError('Replay must remain paused during observation')
            snap=reader.snapshot();rows=[r for r in snap['items'] if r['constructed_local'] and r['map']==a.map]
            item=dict(elapsed_seconds=round(time.monotonic()-started,2),current_map=snap['map'],
                target_local_records=len(rows),native_total_records=snap['count'],
                ttl_min=min((r['ttl'] for r in rows),default=None),ttl_max=max((r['ttl'] for r in rows),default=None),
                flags=dict(collections.Counter(str(r['flags'] & 0x1f) for r in rows)))
            report['observations'].append(item)
            if not rows and len(report['observations'])>1 and report['observations'][0]['target_local_records']:
                report['natural_clear_observed']=True
            report['finished']=report['natural_clear_observed']
            pending=output.with_suffix('.pending');pending.write_text(json.dumps(report,indent=2)+'\n');pending.replace(output)
            print(json.dumps(item),flush=True)
            if report['natural_clear_observed']:break
            time.sleep(10)
        if not report['natural_clear_observed']:report['incomplete_reason']='Bound elapsed without full target-cache removal'
    except Exception as error:
        report['error_type']=type(error).__name__;report['error']=str(error)
    finally:
        reader.close();report['finished']=True
        report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        pending=output.with_suffix('.pending');pending.write_text(json.dumps(report,indent=2)+'\n');pending.replace(output)


if __name__=='__main__':main()
