"""Evaluate bounded arithmetic routines in an emulator, never in the game.

VM_READ only, exact-version offline Reader guard; fetches executable code pages
and .rdata constants into a private emulator. No process writes/remote calls,
credentials, raw memory dumps, or sockets. Output contains numeric protocol
constants only and stays in private research storage.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT/'build/research/protocol-python-libs'))
import pefile
from observe import Reader
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_MEM_UNMAPPED
from unicorn.x86_const import UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RSP


def evaluate(reader, image, rva, argument, setup=None):
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    uc.mem_map(0x100000, 0x200000)
    uc.mem_map(0x400000, 0x1000)
    stack = 0x2ff008
    uc.mem_write(stack, struct.pack('<Q', 0x400000))
    uc.reg_write(UC_X86_REG_RSP, stack)
    uc.reg_write(UC_X86_REG_RCX, argument)
    if setup:setup(uc)
    pages = set()
    def missing(engine, access, address, size, value, data):
        relative = address-reader.base
        section = image.get_section_by_rva(relative)
        if section is None or not (section.Characteristics & 0x20000000 or section.Name.rstrip(b'\0') == b'.rdata'):
            raise RuntimeError(f'Non-code/constant emulator read refused, RVA {relative:#x}')
        page = address & ~4095
        if page in pages or len(pages) >= 128:
            raise RuntimeError('Emulator page budget')
        pages.add(page)
        engine.mem_map(page, 4096)
        engine.mem_write(page, reader.read(page, 4096))
        return True
    uc.hook_add(UC_HOOK_MEM_UNMAPPED, missing)
    uc.emu_start(reader.base+rva, 0x400000, timeout=5_000_000, count=200_000)
    from unicorn.x86_const import UC_X86_REG_RIP
    if uc.reg_read(UC_X86_REG_RIP) != 0x400000:
        raise RuntimeError('Arithmetic routine did not return within budget')
    return uc.reg_read(UC_X86_REG_RAX) & 0xffffffff, len(pages)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output', required=True);a=p.parse_args()
    output=Path(a.output).resolve()
    if not output.is_relative_to(ROOT/'build/research/protocol-private') or output.exists():
        raise ValueError('New private research output required')
    reader=Reader()
    try:
        reader.snapshot()  # includes strict offline/EAC/image gates
        image=pefile.PE(next(m[3] for m in reader.modules if m[0].lower()=='eldenring.exe'),fast_load=True)
        u32=lambda x:x&0xffffffff
        v,pages=evaluate(reader,image,0x1e1a120,0xa4ca8e5b)
        d=u32(v-0x286b342)^0xacd03715
        argument=u32(u32(d<<6)+u32((d>>2)+0x43020814))^d
        first,n=evaluate(reader,image,0x1e1bbc0,argument);pages+=n
        second,n=evaluate(reader,image,0x1e1c250,0x5c82eb1f);pages+=n
        v,n=evaluate(reader,image,0x1e1ae40,0xc415fefe);pages+=n
        third=u32((u32(v+0x8c29e444)^0x6b4c7d2d)-0x12444840)^0x934dc1c
        result=dict(source='exact-image pure arithmetic emulation under offline read gate',
                    first_three_session_fields=[first,second,third],code_pages_fetched=pages,
                    actual_game_function_calls=0,network_requests=0)
        output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(arithmetic_emulation='passed',code_pages_fetched=pages,
                             output='private numeric research JSON',actual_game_function_calls=0)))
    finally:reader.close()


if __name__=='__main__':main()
