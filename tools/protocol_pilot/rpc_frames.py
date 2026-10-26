"""Bounded response routing and durable anonymous checkpoints. No sockets here.

Only the verified heartbeat shape is discarded. Push bodies remain unverified
and stop the run without retaining content. No guessed acknowledgements.
Unknown kinds/sequences fail closed, with numeric header metadata only.
"""
import asyncio
import json
import struct
import time
from pathlib import Path
from wire import response_header


async def await_response(transport,sequence,variant,events,completed=(),timeout=15):
    deadline=time.monotonic()+timeout
    for _ in range(16):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Expected RPC response deadline')
        raw=await asyncio.wait_for(transport.receive(),remaining)
        if not isinstance(raw,bytes) or not raw:raise ValueError('Invalid application frame')
        kind=raw[0];meta=dict(kind=kind,bytes=len(raw))
        if kind==6:
            events.append(dict(frame='unverified_push_rejected',**meta))
            raise ValueError('Unverified push frame layout; collection stopped')
        if kind==7:
            if len(raw)>2:raise ValueError('Unknown heartbeat frame layout')
            events.append(dict(frame='heartbeat_discarded',**meta));continue
        if kind!=5 or len(raw)<5:
            events.append(dict(frame='unknown_rejected',**meta))
            raise ValueError('Unexpected application frame kind '+str(kind))
        found=struct.unpack_from('<I',raw,1)[0]
        if found!=sequence:
            if found in completed:
                events.append(dict(frame='completed_response_discarded',sequence=found,**meta));continue
            events.append(dict(frame='unknown_sequence_rejected',sequence=found,**meta))
            raise ValueError('Unexpected RPC response sequence '+str(found))
        response_header(raw,sequence,variant)
        return raw
    raise RuntimeError('Application frame routing budget exhausted')


class CandidateCheckpoint:
    def __init__(self,path,maximum_records=20000):
        self.path=Path(path)
        if not 1<=maximum_records<=50000:raise ValueError('Checkpoint record budget')
        self.maximum_records=maximum_records
        if self.path.exists():raise ValueError('New candidate checkpoint required')
    def save(self,records,stages,finished=False,reason=None):
        from capture_client_cache import FIELDS,semantics
        if len(records)>self.maximum_records:raise ValueError('Candidate count budget')
        for r in records:
            if set(r)!=set(FIELDS)|{'candidate_key'}:raise ValueError('Anonymous checkpoint allowlist')
            semantics(r)
        data=dict(type='unverified_independent_protocol_candidates',official_samples=0,
            records=records,stages=stages,finished=finished,finish_reason=reason,
            warning='Finite responses; target/native UI correspondence pending. Not full-world coverage.')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.pending')
        temporary.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        temporary.replace(self.path)
