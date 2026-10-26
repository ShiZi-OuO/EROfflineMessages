"""Finite external ETW captures, no game input/injection/settings changes."""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from observe import Reader
from analyze_frames import summarize

p=argparse.ArgumentParser()
p.add_argument('--condition',required=True)
p.add_argument('--runs',type=int,default=3)
p.add_argument('--seconds',type=int,default=120)
p.add_argument('--output',required=True)
p.add_argument('--wait-clean-baseline',action='store_true',help='Wait for prior constructed cache to expire naturally; requires no replay DLL')
a=p.parse_args()
if not 1<=a.runs<=3 or not 3<=a.seconds<=120:raise ValueError('Capture budget')
root=Path(__file__).resolve().parent.parent
present=root/'tools/local/PresentMon-2.6.0-x64.exe'
if hashlib.sha256(present.read_bytes()).hexdigest()!='b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af':raise RuntimeError('Tool digest mismatch')
output=Path(a.output).resolve();output.mkdir(parents=True,exist_ok=False)
r=Reader()
results=[]
try:
    if a.wait_clean_baseline:
        deadline=time.monotonic()+360
        preparation=[]
        while True:
            snap=r.snapshot()
            if any(name.lower()=='erofflinemessages.dll' for name in snap['loaded_mods']):raise RuntimeError('Clean baseline requires no replay DLL')
            count=sum(item['constructed_local'] for item in snap['items'])
            event=dict(timestamp=datetime.datetime.now().astimezone().isoformat(),constructed_cached=count,database_count=snap['count'])
            preparation.append(event)
            print(f'BASELINE SETTLE: {count} prior constructed records; waiting for native expiry only',flush=True)
            (output/'baseline-preparation.json').write_text(json.dumps(preparation,indent=2)+'\n',encoding='utf-8')
            if count==0:break
            if time.monotonic()>=deadline:raise RuntimeError('Prior cache did not naturally clear within 360 s; no benchmark collected')
            time.sleep(20)
    for index in range(1,a.runs+1):
        snap=r.snapshot()
        if snap['map']=='0xffffffff':raise RuntimeError('Map not loaded')
        csv=output/f'{a.condition}-r{index}.csv'
        session=f'EROfflineMessages-{r.pid}-{index}'
        metadata=dict(condition=a.condition,run=index,pid=r.pid,
            started=datetime.datetime.now().astimezone().isoformat(),map=snap['map'],
            havok_position=snap['position_candidate'],player_yaw=snap['yaw_candidate'],
            offline=snap['offline'],database_count=snap['count'],
            constructed_records=sum(item['constructed_local'] for item in snap['items']),
            mod_modules=snap['loaded_mods'],scenario='fixed camera static scene; not a movement-route test')
        graphics=Path(os.environ['APPDATA'])/'EldenRing/GraphicsConfig.xml'
        graphics_bytes=graphics.read_bytes()
        metadata['graphics_sha256']=hashlib.sha256(graphics_bytes).hexdigest()
        metadata['graphics']={node.tag:node.text for node in ET.fromstring(graphics_bytes).iter() if len(node)==0}
        (output/f'{a.condition}-r{index}-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
        print(f'START {a.condition} {index}/{a.runs}: 5 s warmup + {a.seconds} s capture',flush=True)
        command=[str(present),'--process_id',str(r.pid),'--timed',str(a.seconds),
            '--delay','5','--terminate_after_timed','--no_console_stats','--no_track_input',
            '--session_name',session,'--output_file',str(csv)]
        completed=subprocess.run(command,capture_output=True,text=True,errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW)
        (output/f'{a.condition}-r{index}-tool.log').write_text(completed.stdout+completed.stderr,encoding='utf-8')
        if completed.returncode!=0:raise RuntimeError('PresentMon capture failed')
        result=summarize(csv);results.append(result)
        print(f'COMPLETE {index}: {result["frames"]} frames, {result["duration_seconds"]:.2f} s, mean {result["mean_fps"]:.2f} FPS, P99 {result["p99_frame_ms"]:.2f} ms',flush=True)
        (output/'summary.json').write_text(json.dumps(dict(condition=a.condition,runs=results,comparative_acceptance='not_evaluated'),indent=2)+'\n',encoding='utf-8')
finally:r.close()
