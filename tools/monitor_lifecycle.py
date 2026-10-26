"""Bounded offline read monitor. Logs anonymous state changes, never game input."""
import argparse
import datetime
import json
import time
from pathlib import Path
from observe import Reader

p=argparse.ArgumentParser()
p.add_argument('--seconds',type=int,default=900)
p.add_argument('--output',required=True)
args=p.parse_args()
if not 1<=args.seconds<=7200:raise ValueError('Duration budget')
r=Reader()
started=time.monotonic()
previous=None
heartbeat=0
try:
    with Path(args.output).open('a',encoding='utf-8',buffering=1) as output:
        while time.monotonic()-started<args.seconds:
            try:
                s=r.snapshot()
                local=[{k:v for k,v in item.items() if k in ['map','position','flags','ttl','template1','word1','good','poor']} for item in s['items'] if item['constructed_local']]
                for item in local:item['ttl']=round(item['ttl'])
                state=dict(state='offline_observed',map=s['map'],database_count=s['count'],local=local)
            except Exception as error:
                state=dict(state='observation_unavailable',reason=str(error))
            # TTL changes are retained at 30 s heartbeat; structural transitions immediately.
            structural=json.dumps(state,sort_keys=True)
            if state['state']=='offline_observed':
                structural=json.dumps({**state,'local':[{k:v for k,v in item.items() if k!='ttl'} for item in local]},sort_keys=True)
            now=time.monotonic()
            if structural!=previous or now>=heartbeat:
                event=dict(timestamp=datetime.datetime.now().astimezone().isoformat(),elapsed_seconds=round(now-started,2),**state)
                output.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
                previous=structural;heartbeat=now+30
            time.sleep(1)
finally:r.close()
