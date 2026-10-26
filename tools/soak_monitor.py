"""One bounded process run: anonymous cache, bindings and process resource samples."""
import argparse
import datetime
import json
import re
import time
from collections import Counter
from pathlib import Path
from observe import Reader,process_resources,processes

p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=3600);p.add_argument('--output',required=True)
p.add_argument('--runtime-log',help='Optional local mod log; only numeric callback counters are exported')
a=p.parse_args()
if not 30<=a.seconds<=7200:raise ValueError('Soak duration budget')
r=Reader();started=time.monotonic();samples=0;unavailable=0;violations=[]
runtime=None;callback_intervals=0;callback_total=0;latest_counters={}
if a.runtime_log:
    runtime=Path(a.runtime_log).open('r',encoding='utf-8')
    runtime.seek(0,2) # Count only callbacks recorded during this monitored interval.
try:
    with Path(a.output).open('x',encoding='utf-8',buffering=1) as f:
        while time.monotonic()-started<a.seconds:
            event=dict(timestamp=datetime.datetime.now().astimezone().isoformat(),elapsed_seconds=round(time.monotonic()-started,2))
            try:
                if runtime:
                    for line in runtime.readlines(1024*1024):
                        if '[Performance]' not in line:continue
                        fields={k:float(v) for k,v in re.findall(r'(updates|registrations|rebindings|repairs|mod_avg_us|mod_max_us)=([0-9.]+)',line)}
                        if 'updates' in fields:
                            callback_intervals+=1;callback_total+=int(fields['updates']);latest_counters=fields
                    event.update(callback_intervals=callback_intervals,observed_update_callbacks=callback_total,latest_runtime_counters=latest_counters)
                s=r.snapshot();event.update(state='offline_observed',map=s['map'],database_count=s['count'],**process_resources(r.handle))
                local=[item for item in s['items'] if item['constructed_local']]
                event['local_records']=len(local)
                event['bound_local_records']=sum(bool(item['flags']&8) for item in local)
                db=int(s['db'],16);bindings=Counter();total=0
                for offset in [0x60,0x68]:
                    ins=r.u64(r.u64(db+offset)+0x10);seen=set()
                    while ins:
                        if ins in seen or len(seen)>=256:raise RuntimeError('Display chain budget/invariant')
                        seen.add(ins);total+=1
                        if r.u64(ins)!=r.base+0x29cd9e8:raise RuntimeError('Display type mismatch')
                        item=r.u64(ins+0x10)
                        if item and r.u64(item)==r.base+0x29cee88 and r.u32(item+8)==0x7e000001:
                            bindings[r.u64(item+0x40)]+=1
                        ins=r.u64(ins+0x8c8)
                event.update(display_instances=total,local_display_instances=sum(bindings.values()),duplicate_local_bindings=sum(n-1 for n in bindings.values()))
                if event['duplicate_local_bindings'] or s['count']>120:violations.append(event['elapsed_seconds'])
                samples+=1
            except Exception as error:
                event.update(state='observation_unavailable',reason=str(error));unavailable+=1
            f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
            if r.pid not in {pid for pid,_ in processes()}:
                print('Target process exited; ending this process-specific soak',flush=True)
                break
            if (samples+unavailable)%6==0:print(json.dumps(event,ensure_ascii=False),flush=True)
            time.sleep(5)
finally:
    r.close()
    if runtime:runtime.close()
    elapsed=time.monotonic()-started
    summary=dict(pid=r.pid,elapsed_seconds=elapsed,samples=samples,unavailable=unavailable,
        invariant_violation_samples=violations,one_hour_duration_completed=elapsed>=3600,
        callback_intervals=callback_intervals,observed_update_callbacks=callback_total,
        result='requires_resource_trend_analysis_and_game_log_review')
    Path(a.output+'.summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary),flush=True)
