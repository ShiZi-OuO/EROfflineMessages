"""Compare complete static-scene runs, retaining failed and variable results.

Camera matching requires an explicit review of the captured scene screenshots.
This does not certify movement-route or long-run performance.
"""
import argparse
import json
import math
import statistics
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--baseline',required=True)
p.add_argument('--condition',action='append',required=True)
p.add_argument('--scene-reviewed',action='store_true')
p.add_argument('--output',required=True)
a=p.parse_args()

def load(directory):
    root=Path(directory)
    result=json.loads((root/'summary.json').read_text(encoding='utf-8'))
    metadata=[json.loads(path.read_text(encoding='utf-8')) for path in sorted(root.glob('*-metadata.json'))]
    runs=result['runs']
    if len(runs)!=3 or len(metadata)!=3 or not all(x['benchmark_eligible'] for x in runs):
        raise ValueError(f'{root}: requires three complete two-minute runs')
    return dict(directory=str(root),condition=result['condition'],runs=runs,metadata=metadata,
        mean_fps=statistics.mean(x['mean_fps'] for x in runs),
        mean_of_run_p99_ms=statistics.mean(x['p99_frame_ms'] for x in runs),
        fps_sample_sd=statistics.stdev(x['mean_fps'] for x in runs))

baseline=load(a.baseline)
reference=baseline['metadata'][0]
conditions=[]
for directory in a.condition:
    candidate=load(directory)
    reasons=[]
    for m in baseline['metadata']+candidate['metadata']:
        if m['map']!=reference['map']:reasons.append('map differs')
        if m['graphics_sha256']!=reference['graphics_sha256']:reasons.append('graphics configuration differs')
        if math.dist(m['havok_position'],reference['havok_position'])>.25:reasons.append('player positions differ by more than 0.25 m')
        if m['offline']['online'] or m['offline']['menu_online_enabled']:reasons.append('offline state mismatch')
    if any('erofflinemessages.dll' in [name.lower() for name in m['mod_modules']] for m in baseline['metadata']):
        reasons.append('baseline has replay DLL loaded')
    if not a.scene_reviewed:reasons.append('camera screenshots have not been reviewed')
    candidate['fps_drop_percent']=100*(1-candidate['mean_fps']/baseline['mean_fps'])
    candidate['p99_increase_percent']=100*(candidate['mean_of_run_p99_ms']/baseline['mean_of_run_p99_ms']-1)
    candidate['comparability_gaps']=sorted(set(reasons))
    candidate['static_scene_targets_met']=not reasons and candidate['fps_drop_percent']<=3 and candidate['p99_increase_percent']<=10
    candidate['result']='not_comparable' if reasons else ('passed_static_scene_only' if candidate['static_scene_targets_met'] else 'failed_static_scene_targets')
    conditions.append(candidate)
result=dict(metric='Arithmetic mean of all three run mean FPS and all three run P99 values; no runs discarded',
    scope='One fixed-camera scene only; movement route and one-hour soak require separate evidence',
    targets=dict(maximum_fps_drop_percent=3,maximum_p99_increase_percent=10),baseline=baseline,conditions=conditions)
Path(a.output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
for row in conditions:print(f'{row["condition"]}: {row["result"]}; FPS drop {row["fps_drop_percent"]:.3f}%, P99 increase {row["p99_increase_percent"]:.3f}%')
