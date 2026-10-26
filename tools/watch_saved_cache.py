"""Bounded autosave watcher; no game-process access, save writes or sockets.

New semantics remain unverified candidates. Baseline historical records and
local replay records are excluded; a rating change alone is not a new sample.
"""
import argparse
import datetime
import json
import time
from pathlib import Path
from capture_client_cache import fingerprint
from read_saved_cache import normal_save_path,read_consistent


def fresh_records(baseline,observation):
    old={fingerprint(x) for x in baseline['records']}
    return {fingerprint(x):x for x in observation['records'] if fingerprint(x) not in old}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',required=True);p.add_argument('--output',required=True)
    p.add_argument('--stop-file',help='Optional private control file; stop cleanly when it appears')
    p.add_argument('--duration',type=int,default=900);a=p.parse_args()
    root=Path(__file__).resolve().parent.parent;output=Path(a.output).resolve()
    if not output.is_relative_to(root/'build/capture') or output.exists():raise ValueError('New private candidate output required')
    if not 1<=a.duration<=7200:raise ValueError('Collection duration budget')
    stop=Path(a.stop_file).resolve() if a.stop_file else None
    if stop and (not stop.is_relative_to(root/'build/capture') or stop.exists()):raise ValueError('New private stop file required')
    baseline=json.loads(Path(a.baseline).read_text(encoding='utf-8'))
    if baseline['type']!='unverified_saved_cache_observation':raise ValueError('Wrong baseline type')
    source=normal_save_path();state=dict(schema_version=1,type='unverified_saved_cache_candidates',
        official_samples=0,source='normal-client autosave filesystem observations; provenance/UI pending',
        game_process_access=False,save_writes=0,identity_exported=False,raw_save_retained=False,
        observations=0,incomplete_observations=0,records=[],finished=False)
    seen={};previous=None;deadline=time.monotonic()+a.duration
    def write():
        state['records']=[dict(candidate_key=k,**v) for k,v in sorted(seen.items())]
        state['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        temp=output.with_suffix('.pending');temp.write_text(json.dumps(state,indent=2,allow_nan=False)+'\n');temp.replace(output)
    output.parent.mkdir(parents=True,exist_ok=True);write()
    try:
        while time.monotonic()<deadline:
            if stop and stop.exists():
                state['finished']=True;state['finish_reason']='operator_stop_file';break
            if normal_save_path()!=source:raise RuntimeError('Active Steam account changed; collection stopped')
            stat=source.stat();signature=(stat.st_size,stat.st_mtime_ns)
            if signature!=previous:
                try:
                    observation=read_consistent(source)
                    state['observations']+=1
                    if observation['checksum_rejected_slot_indexes']:state['incomplete_observations']+=1
                    before=len(seen);seen.update(fresh_records(baseline,observation));previous=signature
                    write()
                    print(json.dumps(dict(observations=state['observations'],candidates=len(seen),
                        newly_added=len(seen)-before,maps=len({v['map'] for v in seen.values()}))),flush=True)
                except (RuntimeError,ValueError,OSError):
                    state['incomplete_observations']+=1
            time.sleep(1)
        else:state['finished']=True;state['finish_reason']='duration_elapsed'
    except KeyboardInterrupt:state['finished']=True;state['finish_reason']='operator_stopped'
    finally:write()


if __name__=='__main__':main()
