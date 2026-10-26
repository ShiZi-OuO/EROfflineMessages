"""Fixed-field session configuration diagnostic; offline by default.

The online mode is a NEW action requiring explicit human authorization. It only
attempts ordinary QUERY_INFORMATION|VM_READ once. Access refusal ends the run;
there is no driver, injection, patch, ticket read, EAC change or bypass. Unknown
scalar values may be identifying: private output only, never print or package.
This tool sends no requests and cannot extend the existing protocol pilot cap.
"""
import argparse
import ctypes as c
import hashlib
import json
import struct
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from observe import Reader, K, modules, processes

SHA = 'f9118fea2cfd8fa3901e8060bfadb1552cb2471771ded8a5b662c4e298ffb328'


def fields(reader):
    q = reader.u64
    base = reader.base
    manager = q(base+0x3d74f28)
    root = q(manager)
    if q(root) != base+0x3082cc8:raise ValueError('FN client type mismatch')
    proxy = q(root+8)
    if q(proxy) != base+0x3085590:raise ValueError('FN proxy type mismatch')
    module = q(proxy+0x170)
    if q(module) != base+0x308c148:raise ValueError('FN module type mismatch')
    head = q(module+0x88);node = q(head)
    seen = set();found = []
    while node != head:
        if node in seen or len(seen) >= 16:raise ValueError('Servant traversal budget')
        seen.add(node);servant = q(node+0x18)
        if servant and q(servant) == base+0x308e288:
            def values():
                return dict(field_68_qword=q(servant+0x68),
                    fields_70_78=list(struct.unpack('<3I',reader.read(servant+0x70,12))),
                    field_7c_byte=reader.read(servant+0x7c,1)[0],
                    fields_198_1a4=list(struct.unpack('<4I',reader.read(servant+0x198,16))))
            before = values()
            if before != values():raise ValueError('Configuration changed during read')
            found.append(before)
        node = q(node)
    if len(found) != 1:raise ValueError('Expected exactly one FN servant')
    return found[0]


class AuthorizedOnlineRead:
    def __init__(self):
        games = [pid for pid,name in processes() if name.lower() == 'eldenring.exe']
        if len(games) != 1:raise RuntimeError('Expected one original game')
        inventory = modules(games[0])
        if any(any(tag in m[0].lower() for tag in ('me3','offline','shstime')) for m in inventory):
            raise RuntimeError('Use the original unmodified client only')
        game = [m for m in inventory if m[0].lower() == 'eldenring.exe']
        if len(game) != 1:raise RuntimeError('Executable inventory denied or ambiguous')
        if hashlib.sha256(Path(game[0][3]).read_bytes()).hexdigest() != SHA:
            raise RuntimeError('Unsupported image')
        self.base = game[0][1]
        self.handle = K.OpenProcess(0x410,False,games[0])
        if not self.handle:raise RuntimeError('Ordinary read access refused; stopping without bypass')
        self.read_count = 0
        try:
            manager = self.u64(self.base+0x3d709a8)
            if self.read(manager+0xbc8,1) != b'\x01':
                raise RuntimeError('Expected logged-in original client')
        except Exception:
            self.close();raise
    def read(self,address,size):
        self.read_count += 1
        if self.read_count > 128:raise ValueError('Total read call budget')
        if not 0 < size <= 16 or address < 0x10000:raise ValueError('Fixed-field read budget')
        data = c.create_string_buffer(size);got = c.c_size_t()
        if not K.ReadProcessMemory(self.handle,c.c_void_p(address),data,size,c.byref(got)) or got.value != size:
            raise RuntimeError('Fixed-field read refused; stopping without retry')
        return data.raw
    def u64(self,address):return struct.unpack('<Q',self.read(address,8))[0]
    def close(self):K.CloseHandle(self.handle)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    p.add_argument('--authorized-online-read',action='store_true',
        help='Use ONLY after explicit human approval for one original online process observation')
    a = p.parse_args();output = Path(a.output).resolve()
    private = ROOT/'build/research/protocol-private'
    if not output.is_relative_to(private) or output.exists():raise ValueError('New private output required')
    private.mkdir(parents=True,exist_ok=True)
    reader = None
    try:
        if a.authorized_online_read:
            # Separate one-shot ledger, never resets/changes the RPC budget.
            with (private/'online-config-read-attempt.json').open('x') as f:
                json.dump(dict(action='one ordinary read-only online config observation',attempts=1),f)
            reader = AuthorizedOnlineRead()
        else:
            reader = Reader();reader.snapshot()
        result = fields(reader)
        result.update(source='fixed-field original client read',game_sha256=SHA,
            online_mode=a.authorized_online_read,field_semantics_unverified=True,
            private_only=True,process_writes=0,requests=0)
        with output.open('x') as f:json.dump(result,f,indent=2)
        print(json.dumps(dict(result='fixed fields captured privately',online_mode=a.authorized_online_read,
            process_writes=0,requests=0,raw_values_printed=False)))
    except (RuntimeError,ValueError,OSError) as error:
        print(json.dumps(dict(result='diagnostic refused or incomplete',automatic_retry=False,
            bypass_attempted=False,raw_values_printed=False,
            reason=str(error) if isinstance(error,(RuntimeError,ValueError)) else 'File or OS operation failed')))
        raise SystemExit(1)
    finally:
        if reader:reader.close()


if __name__ == '__main__':main()
