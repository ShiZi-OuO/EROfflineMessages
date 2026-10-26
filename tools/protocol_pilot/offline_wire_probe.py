"""Compare the local native session writer in an emulator with our fake-byte encoder.

No game calls/writes/network/tickets. Supplies synthetic structures in emulator
memory, intercepts only primitive byte output and fixed Steam variant dispatch.
"""
import json
import argparse
import struct
from pathlib import Path
from offline_math_probe import Reader, evaluate, pefile, ROOT
from wire import create_session
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_R8, UC_X86_REG_RIP, UC_X86_REG_RSP


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',type=lambda x:int(x,0),default=0x1122334455667788)
    parser.add_argument('--report',default=str(ROOT/'evidence/protocol-pilot-native-wire.json'))
    args=parser.parse_args();report=Path(args.report).resolve()
    if not 0<=args.version<1<<64 or not report.is_relative_to(ROOT/'evidence') or report.exists():
        raise ValueError('New bounded evidence output and u64 version required')
    reader=Reader()
    try:
        reader.snapshot()
        image=pefile.PE(next(m[3] for m in reader.modules if m[0].lower()=='eldenring.exe'),fast_load=True)
        output=bytearray();dispatch=[]
        def setup(uc):
            source=0x180000;ticket=0x181000
            data=bytearray(0xc8)
            struct.pack_into('<3I',data,0,11,22,33)
            struct.pack_into('<Q',data,0x10,args.version)
            struct.pack_into('<3Q',data,0x18,ticket,ticket+4,ticket+4)
            struct.pack_into('<I',data,0x78,1)
            struct.pack_into('<IB',data,0x80,2,1)
            struct.pack_into('<2I',data,0x88,3,4);data[0x90]=1
            struct.pack_into('<2Q',data,0xa8,0,15)
            struct.pack_into('<4I',data,0xb8,5,6,7,8)
            uc.mem_write(source,bytes(data));uc.mem_write(ticket,b'FAKE')
            uc.reg_write(UC_X86_REG_RDX,source)
            def code(engine,address,size,unused):
                relative=address-reader.base
                if relative==0x1e448c0:
                    n=engine.reg_read(UC_X86_REG_R8)
                    if n>4096 or len(output)+n>8192:raise RuntimeError('Synthetic output budget')
                    output.extend(engine.mem_read(engine.reg_read(UC_X86_REG_RDX),n))
                    sp=engine.reg_read(UC_X86_REG_RSP)
                    target=struct.unpack('<Q',engine.mem_read(sp,8))[0]
                    engine.reg_write(UC_X86_REG_RSP,sp+8);engine.reg_write(UC_X86_REG_RIP,target)
                    engine.reg_write(UC_X86_REG_RAX,1)
                elif relative==0x1e3a130:
                    kind=engine.reg_read(UC_X86_REG_RCX);dispatch.append(kind)
                    if kind!=1:raise RuntimeError('Unexpected synthetic ticket variant')
                    # Exact-image dispatch table case 1 -> vector-byte writer thunk.
                    engine.reg_write(UC_X86_REG_RCX,engine.reg_read(UC_X86_REG_RDX))
                    engine.reg_write(UC_X86_REG_RDX,engine.reg_read(UC_X86_REG_R8))
                    engine.reg_write(UC_X86_REG_RIP,reader.base+0x1e39890)
            uc.hook_add(UC_HOOK_CODE,code)
        _,pages=evaluate(reader,image,0x1e3e360,0x190000,setup)
        expected=create_session(1,[11,22,33],args.version,b'FAKE',
            platform=2,region=3,language=4,cross_region=True,flags=True,tail=(5,6,7,8))[9:]
        if output!=expected:raise RuntimeError('Native synthetic body differs from independent encoder')
        result=dict(native_writer_rva='0x1e3e360',native_writer_emulated=True,
            fake_ticket_only=True,game_function_calls=0,network_requests=0,
            body_bytes=len(output),byte_for_byte_match=True,steam_variant_dispatch=dispatch,version_argument=args.version,
            code_pages_fetched=pages,note='Checks layout only, not correct live version/platform field values or authentication success')
        report.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    finally:reader.close()


if __name__=='__main__':main()
