"""Offline-only read observation. Opens the game with QUERY_INFORMATION | VM_READ only.

No WriteProcessMemory, remote threads, breakpoints, or game calls. Export allowlisted
anonymous semantics; never dump message appearance, account IDs, player names or saves.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import struct
import time
from pathlib import Path

K = c.WinDLL('kernel32', use_last_error=True)
K.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];K.CreateToolhelp32Snapshot.restype=w.HANDLE
K.CloseHandle.argtypes=[w.HANDLE];K.CloseHandle.restype=w.BOOL
K.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];K.OpenProcess.restype=w.HANDLE
K.ReadProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)];K.ReadProcessMemory.restype=w.BOOL
class PROCESS(c.Structure):
    _fields_=[('size',w.DWORD),('usage',w.DWORD),('pid',w.DWORD),('heap',c.c_size_t),('module',w.DWORD),('threads',w.DWORD),('parent',w.DWORD),('priority',w.LONG),('flags',w.DWORD),('name',w.WCHAR*260)]
class MODULE(c.Structure):
    _fields_=[('size',w.DWORD),('id',w.DWORD),('pid',w.DWORD),('global_usage',w.DWORD),('usage',w.DWORD),('base',c.c_void_p),('base_size',w.DWORD),('handle',w.HMODULE),('name',w.WCHAR*256),('path',w.WCHAR*260)]
K.Process32FirstW.argtypes=[w.HANDLE,c.POINTER(PROCESS)];K.Process32NextW.argtypes=[w.HANDLE,c.POINTER(PROCESS)]
K.Module32FirstW.argtypes=[w.HANDLE,c.POINTER(MODULE)];K.Module32NextW.argtypes=[w.HANDLE,c.POINTER(MODULE)]
class MEMORY(c.Structure):
    _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD)]+[(name,c.c_size_t) for name in
        ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
         'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage']]
K.K32GetProcessMemoryInfo.argtypes=[w.HANDLE,c.POINTER(MEMORY),w.DWORD];K.K32GetProcessMemoryInfo.restype=w.BOOL
K.GetProcessTimes.argtypes=[w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)];K.GetProcessTimes.restype=w.BOOL

def process_resources(handle):
    memory=MEMORY();memory.cb=c.sizeof(memory)
    created,exited,kernel,user=(w.FILETIME() for _ in range(4))
    if not K.K32GetProcessMemoryInfo(handle,c.byref(memory),memory.cb) or not K.GetProcessTimes(handle,c.byref(created),c.byref(exited),c.byref(kernel),c.byref(user)):
        raise c.WinError(c.get_last_error())
    def ticks(value):return (value.dwHighDateTime<<32)|value.dwLowDateTime
    return dict(private_bytes=memory.PrivateUsage,working_set_bytes=memory.WorkingSetSize,
        cpu_seconds=(ticks(kernel)+ticks(user))/1e7)

def processes():
    h=K.CreateToolhelp32Snapshot(2,0);p=PROCESS();p.size=c.sizeof(p);out=[]
    try:
        ok=K.Process32FirstW(h,c.byref(p))
        while ok:
            out.append((p.pid,p.name));ok=K.Process32NextW(h,c.byref(p))
    finally:K.CloseHandle(h)
    return out

def modules(pid):
    h=K.CreateToolhelp32Snapshot(0x18,pid);m=MODULE();m.size=c.sizeof(m);out=[]
    try:
        ok=K.Module32FirstW(h,c.byref(m))
        while ok:
            out.append((m.name,m.base,m.base_size,m.path));ok=K.Module32NextW(h,c.byref(m))
    finally:K.CloseHandle(h)
    return out

class Reader:
    def __init__(self):
        ps=processes()
        if any('easyanticheat' in name.lower() or name.lower()=='start_protected_game.exe' for _,name in ps):
            raise RuntimeError('Anti-cheat process present: observation refused')
        games=[pid for pid,name in ps if name.lower()=='eldenring.exe']
        if len(games)!=1:raise RuntimeError('Expected exactly one game')
        self.pid=games[0];self.modules=modules(self.pid)
        exe=next(x for x in self.modules if x[0].lower()=='eldenring.exe');self.base=exe[1]
        self.sha=hashlib.sha256(Path(exe[3]).read_bytes()).hexdigest()
        if self.sha!='f9118fea2cfd8fa3901e8060bfadb1552cb2471771ded8a5b662c4e298ffb328':raise RuntimeError('Unsupported executable')
        self.handle=K.OpenProcess(0x410,False,self.pid)
        if not self.handle:raise c.WinError(c.get_last_error())
        self.next_guard=0
    def close(self):K.CloseHandle(self.handle)
    def read(self,address,size):
        if address<0x10000 or size<0 or size>1048576:raise ValueError('Read budget')
        buffer=c.create_string_buffer(size);n=c.c_size_t()
        if not K.ReadProcessMemory(self.handle,address,buffer,size,c.byref(n)) or n.value!=size:raise c.WinError(c.get_last_error())
        return buffer.raw
    def unpack(self,address,fmt):return struct.unpack(fmt,self.read(address,struct.calcsize(fmt)))
    def u64(self,a):return self.unpack(a,'<Q')[0]
    def u32(self,a):return self.unpack(a,'<I')[0]
    def offline(self):
        gm=self.u64(self.base+0x3d709a8);data=self.u64(self.base+0x3d64fb8);settings=self.u64(data+0x58)
        online,server=self.unpack(gm+0xbc8,'<BB');start_offline=self.unpack(settings+0x18,'<B')[0]
        menu_online=self.unpack(self.base+0x458fb9c,'<B')[0]
        initialized=self.unpack(self.base+0x458fba0,'<i')[0]
        return dict(online=online,server_connection_enabled=server,start_offline_setting_unused_by_me3=start_offline,menu_online_enabled=menu_online,menu_property_initialized=initialized)
    def snapshot(self):
        now=time.monotonic()
        if now>=self.next_guard:
            if any('easyanticheat' in name.lower() or name.lower()=='start_protected_game.exe' for _,name in processes()):
                raise RuntimeError('Anti-cheat detected: observation refused')
            self.next_guard=now+5
        guard=self.offline()
        # MSVC completed thread-safe static initialization uses an epoch <= -2.
        # 0 means never initialized; -1 means initialization is in progress.
        if guard['online']!=0 or guard['menu_online_enabled']!=0 or guard['menu_property_initialized']>=-1:raise RuntimeError('Offline guard not satisfied: '+str(guard))
        net=self.u64(self.base+0x3d61ee0)
        if self.u64(net)!=self.base+0x29cfeb8:raise RuntimeError('NetMan vtable mismatch')
        db=self.u64(net+0x78)
        if self.u64(db)!=self.base+0x29cec68:raise RuntimeError('Message DB vtable mismatch')
        head=self.u64(db+0x10);node=self.u64(head);previous=head;items=[]
        while node!=head:
            if len(items)>=4096:raise RuntimeError('Node traversal budget')
            nxt,prev,item=self.unpack(node,'<QQQ')
            if prev!=previous or self.u64(item)!=self.base+0x29cee88:raise RuntimeError('List invariant')
            mapid,area=self.unpack(item+0x14,'<II');pos=self.unpack(item+0x1c,'<4f');phrase=self.unpack(item+0x2c,'<8H')
            items.append(dict(constructed_local=self.u32(item+8)==0x7e000001,map=mapid,secondary_area=area,area=self.u32(item+0x48),position=list(pos[:3]),yaw=pos[3],template1=phrase[0],gesture=phrase[1]&255,word1=phrase[2],conjunction=phrase[3],template2=phrase[4],word2=phrase[5],good=phrase[6],poor=phrase[7],ttl=self.unpack(item+0x220,'<f')[0],flags=self.u32(item+0x224)))
            previous=node;node=nxt
        if self.u64(head+8)!=previous:raise RuntimeError('Tail invariant')
        return dict(pid=self.pid,sha256=self.sha,offline=guard,net=hex(net),db=hex(db),map=hex(self.u32(net+0x1c)),region=self.u32(net+0x24),position_candidate=list(self.unpack(net+0x28,'<3f')),yaw_candidate=self.unpack(net+0x34,'<f')[0],managers=[hex(self.u64(db+0x60)),hex(self.u64(db+0x68))],count=self.u64(db+0x18),items=items,loaded_mods=[x[0] for x in self.modules if any(t in x[0].lower() for t in ['me3','offline','shs','camera'])])

def main():
    p=argparse.ArgumentParser();p.add_argument('--output');args=p.parse_args()
    reader=Reader()
    try:
        result=reader.snapshot();text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
        if args.output:Path(args.output).write_text(text+'\n',encoding='utf-8')
        print(text)
    finally:reader.close()
if __name__=='__main__':main()
