"""Summarize numeric mod timing intervals; these are not frame-rate results."""
import argparse
import json
import re
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('log');p.add_argument('--output',required=True);a=p.parse_args()
text=Path(a.log).read_text(encoding='utf-8')
# Logs append across normal restarts. Report the latest loaded session only.
lines=text.splitlines();starts=[i for i,line in enumerate(lines) if '[Loaded]' in line]
if not starts:raise ValueError('No loaded session')
lines=lines[starts[-1]:]
phases={key:dict(calls=0,total_us=0.0,maximum_us=0) for key in ['registration','maintenance','cache_repair']}
updates=0;total_us=0.0;maximum=0;peak_native=0;peak_local=0;events=[];last_counts={}
for line in lines:
    if '[Performance]' in line:
        fields={k:float(v) for k,v in re.findall(r'(mod_avg_us|mod_max_us|updates|generations|registrations|rebindings|repairs)=([0-9.]+)',line)}
        count=int(fields['updates']);updates+=count;total_us+=count*fields['mod_avg_us'];maximum=max(maximum,fields['mod_max_us']);last_counts=fields
    if '[WorkPhases]' in line:
        peak_native=max(peak_native,int(re.search(r'native_items=(\d+)',line)[1]))
        peak_local=max(peak_local,int(re.search(r'local_cached=(\d+)',line)[1]))
        for key,values in phases.items():
            match=re.search(r'\b'+key+r'_calls=(\d+)_avg_us=([0-9.]+)_max_us=(\d+)',line)
            if not match:raise ValueError('Malformed work phase interval')
            count=int(match[1]);values['calls']+=count;values['total_us']+=count*float(match[2]);values['maximum_us']=max(values['maximum_us'],int(match[3]))
    if any(tag in line for tag in ['[Scene]','[Registered]','[CacheRepair]','[Disabled]']):events.append(line)
for values in phases.values():values['mean_us']=values['total_us']/values['calls'] if values['calls'] else None
result=dict(loaded=lines[0],scope='Latest session, completed 10-second numeric intervals; excludes native original update time; no FPS inference',
    observed_update_callbacks=updates,mean_mod_callback_us=total_us/updates if updates else None,maximum_mod_callback_us=maximum,
    work_phases=phases,peak_native_items=peak_native,peak_local_cached=peak_local,last_counters=last_counts,events=events)
Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
print(json.dumps(dict(observed_updates=updates,mean_mod_us=result['mean_mod_callback_us'],maximum_mod_us=maximum,phases=phases,last_counters=last_counts),indent=2))
