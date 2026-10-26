"""Read-only anonymous cache extraction from normal PC autosaves.

Independent narrow format reader, based on this project's native serializer
analysis (1be220/1bd630). No editor library imports. Never writes saves, retains
raw saves, opens a game process, exports identities, or contacts a server.
Output is unverified cache data until normal-client receipt/UI corroboration.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import struct
from pathlib import Path
from capture_client_cache import fingerprint, semantics

SLOT_START=0x300
SLOT_SIZE=0x280010
NET_SIZE=0x20004
PREFIX=struct.pack('<IHHIII',2,2,0,8,65535,0)
CHUNKS=((2,0),(5,0),(6,2),(8,0),(9,0),(7,1))


def cache_region(slot):
    """Require one complete native chunk chain; do not salvage damaged saves."""
    found=[];start=0
    while (offset:=slot.find(PREFIX,start))>=0:
        start=offset+4
        if offset+NET_SIZE>len(slot):continue
        cur=offset+4;payload=None
        for kind,version in CHUNKS:
            if cur+8>offset+NET_SIZE:break
            k,v,n=struct.unpack_from('<HHI',slot,cur)
            if (k,v)!=(kind,version) or n%4 or cur+8+n>offset+NET_SIZE:break
            if kind==6:payload=slot[cur+8:cur+8+n]
            cur+=8+n
        else:
            if slot[cur:cur+8]==struct.pack('<HHI',65535,0,0) and not any(slot[cur+8:offset+NET_SIZE]):found.append(payload)
    if len(found)>1:raise ValueError('Ambiguous serialized message region')
    return found[0] if found else None


def entries(payload):
    cur=0;records=[];local=0
    while cur+8<=len(payload):
        kind,size=struct.unpack_from('<II',payload,cur);cur+=8
        if kind==65535:
            if size or cur!=len(payload):raise ValueError('Invalid subentry terminator')
            return records,local
        if size>len(payload)-cur:raise ValueError('Truncated serialized subentry')
        body=payload[cur:cur+size];cur=(cur+size+3)&~3
        if kind!=1:continue  # own messages and session identifiers never exported
        if size not in (602,606):raise ValueError('Unknown native cached-message layout')
        shift=size-602
        if shift and body[:shift]!=bytes(shift):raise ValueError('Unexpected alignment prefix')
        data=body[shift:shift+512]
        if struct.unpack_from('<I',data,0x1b4)[0]==0x7e000001:
            local+=1;continue
        map_id,secondary=struct.unpack_from('<2I',data,0x1c0)
        area=struct.unpack_from('<I',data,0x1f8)[0]
        if not map_id or map_id==0xffffffff or not area:continue
        phrase=struct.unpack_from('<8H',data,0x1d8)
        value=semantics(dict(map=map_id,area=area,secondary_area=secondary,
            position=list(struct.unpack_from('<3f',data,0x1c8)),
            yaw=struct.unpack_from('<f',data,0x1d4)[0],template1=phrase[0],word1=phrase[2],
            conjunction=phrase[3],template2=phrase[4],word2=phrase[5],good=phrase[6],poor=phrase[7]))
        if not value['template1'] or value['good']>9999 or value['poor']>9999:raise ValueError('Invalid native semantic fields')
        records.append(value)
    raise ValueError('Unterminated serialized message list')


def parse_save(data):
    if data[:4]!=b'BND4' or not 28_000_000<=len(data)<=32_000_000:
        raise ValueError('Unsupported normal PC save envelope')
    records={};counts=[];local=0;invalid=[]
    for slot in range(10):
        begin=SLOT_START+slot*SLOT_SIZE
        content=data[begin+16:begin+SLOT_SIZE]
        if len(content)!=SLOT_SIZE-16:raise ValueError('Slot bounds')
        if not any(content):continue
        if hashlib.md5(content).digest()!=data[begin:begin+16]:
            invalid.append(slot);continue
        payload=cache_region(content)
        if payload is None:continue
        values,n=entries(payload);local+=n;counts.append(dict(slot_index=slot,anonymous_nonreplay_records=len(values),local_replay_excluded=n))
        for value in values:records[fingerprint(value)]=value
    # An older unused slot may already fail its checksum. Never repair it and
    # never let it contribute candidates; a later complete autosave may retry it.
    return dict(records=list(records.values()),slot_counts=counts,
                checksum_rejected_slot_indexes=invalid,local_replay_excluded=local)


def normal_save_path():
    # Local Steam metadata only. Do not load a Steam DLL, generate a ticket, or
    # expose the account folder name merely to locate the user's own normal save.
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam\ActiveProcess') as key:
        account=winreg.QueryValueEx(key,'ActiveUser')[0]
    if not account:raise RuntimeError('No active Steam user')
    path=Path(os.environ['APPDATA'])/'EldenRing'/str(76561197960265728+account)/'ER0000.sl2'
    if not path.is_file():raise RuntimeError('Current Steam account normal save not found')
    return path


def read_consistent(path):
    before=path.stat();data=path.read_bytes();after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise RuntimeError('Autosave changed during read; no partial data admitted')
    return parse_save(data)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent.parent;output=Path(a.output).resolve()
    if not output.is_relative_to(root/'build/capture') or output.exists():raise ValueError('Use a new private output under build/capture')
    result=read_consistent(normal_save_path())
    result.update(schema_version=1,type='unverified_saved_cache_observation',official_samples=0,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),save_writes=0,
        game_process_access=False,identity_exported=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(records=len(result['records']),slot_counts=result['slot_counts'],
        checksum_rejected_slot_indexes=result['checksum_rejected_slot_indexes'],
        local_replay_excluded=result['local_replay_excluded'],official_samples=0,save_writes=0)))


if __name__=='__main__':main()
