"""Summarize real PresentMon CSV frames; short probes cannot pass benchmarks."""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

def summarize(path):
    chains=defaultdict(list)
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            if row.get('Application','').lower()!='eldenring.exe':continue
            try:
                dt=float(row['MsBetweenPresents'])
                timestamp=float(row['TimeInMs'])
            except (ValueError,KeyError):continue
            if not math.isfinite(dt) or not math.isfinite(timestamp) or dt<=0:continue
            chains[row.get('SwapChainAddress','')].append((timestamp,dt))
    if not chains:raise ValueError('No valid game frames')
    frames=max(chains.values(),key=len)
    duration=(max(t for t,_ in frames)-min(t for t,_ in frames))/1000
    times=[dt for _,dt in frames]
    ordered=sorted(times)
    index=(len(ordered)-1)*.99
    lo=int(index);hi=min(lo+1,len(ordered)-1)
    p99=ordered[lo]+(ordered[hi]-ordered[lo])*(index-lo)
    return dict(file=str(path),frames=len(times),duration_seconds=duration,
        mean_fps=1000/statistics.mean(times),mean_frame_ms=statistics.mean(times),
        p99_frame_ms=p99,maximum_frame_ms=max(times),
        benchmark_eligible=duration>=115 and len(times)>=1000,
        metric='MsBetweenPresents, dominant swap chain; all captured valid frames')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('files',nargs='+');p.add_argument('--output');a=p.parse_args()
    data=dict(runs=[summarize(path) for path in a.files],comparative_acceptance='not_evaluated')
    text=json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)
    if a.output:Path(a.output).write_text(text+'\n',encoding='utf-8')
    print(text)
