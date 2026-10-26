"""Offline read-only disassembly. Allows only verified executable code sections."""
import argparse
from observe import Reader
import capstone
import pefile
p=argparse.ArgumentParser();p.add_argument('rva',type=lambda x:int(x,0));p.add_argument('size',type=lambda x:int(x,0));args=p.parse_args()
if not 0<args.size<=16384:raise ValueError('code read budget')
r=Reader()
try:
    r.snapshot() # all offline and structure checks must pass
    module=next(m for m in r.modules if m[0].lower()=='eldenring.exe')
    pe=pefile.PE(module[3],fast_load=True);section=pe.get_section_by_rva(args.rva)
    if section is None or not section.Characteristics&0x20000000 or args.rva+args.size>section.VirtualAddress+section.Misc_VirtualSize:raise ValueError('Not one executable section')
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
    for i in md.disasm(r.read(r.base+args.rva,args.size),r.base+args.rva):print(f'{i.address-r.base:08x} {i.mnemonic:8} {i.op_str}')
finally:r.close()
