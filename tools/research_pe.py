"""Read-only PE/RTTI/disassembly helpers. Never attach to a game process."""
import argparse
import json
import struct
from pathlib import Path

import capstone
import pefile

DEFAULT_EXE = r"F:\Steam\steamapps\common\ELDEN RING\Game\eldenring.exe"


class Image:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        self.pe = pefile.PE(data=self.data, fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True

    def bytes(self, rva, size):
        off = self.pe.get_offset_from_rva(rva)
        return self.data[off:off+size]

    def hits(self, needle):
        start = 0
        while (pos := self.data.find(needle, start)) >= 0:
            yield pos
            start = pos + 1

    def rtti(self, name):
        pos = self.data.find(name.encode())
        if pos < 0:
            return []
        descriptor = self.pe.get_rva_from_offset(pos - 16)
        result = []
        for ref in self.hits(struct.pack('<I', descriptor)):
            off = ref - 12
            if off < 0:
                continue
            sig, offset, cd, desc, hierarchy, self_rva = struct.unpack_from('<6I', self.data, off)
            rva = self.pe.get_rva_from_offset(off)
            if sig != 1 or desc != descriptor or self_rva != rva:
                continue
            for vtref in self.hits(struct.pack('<Q', self.base+rva)):
                vft = self.pe.get_rva_from_offset(vtref+8)
                methods = []
                for n in range(32):
                    value = struct.unpack_from('<Q', self.data, vtref+8+n*8)[0]
                    method_rva = value-self.base
                    section = self.pe.get_section_by_rva(method_rva)
                    if section is None or not section.Characteristics & 0x20000000:
                        break
                    methods.append(hex(method_rva))
                result.append(dict(name=name, descriptor=hex(descriptor), col=hex(rva), offset=offset, vtable=hex(vft), methods=methods))
        return result

    def disasm(self, rva, size):
        for i in self.md.disasm(self.bytes(rva, size), self.base+rva):
            print(f'{i.address-self.base:08x} {i.mnemonic:8} {i.op_str}')

    def function(self, rva):
        pdata = next(s for s in self.pe.sections if s.Name.startswith(b'.pdata')).get_data()
        for off in range(0, len(pdata)-11, 12):
            begin, end, unwind = struct.unpack_from('<III', pdata, off)
            if begin <= rva < end:
                print(f'FUNCTION {begin:#x}..{end:#x} unwind={unwind:#x}')
                self.disasm(begin, end-begin)
                return
        print('NO RUNTIME FUNCTION; using explicit disassembly range')
        self.disasm(rva, 0x100)

    def refs(self, target):
        # Resolve RIP-relative LEA/MOV candidates without linear-disassembling all 43 MB.
        import re
        for s in self.pe.sections:
            if not s.Characteristics & 0x20000000:
                continue
            data = s.get_data()
            for m in re.finditer(rb'[\x48\x4c][\x8d\x8b\x89][\x05\x0d\x15\x1d\x25\x2d\x35\x3d]', data):
                p = m.start()
                disp = struct.unpack_from('<i', data, p+3)[0]
                rva = s.VirtualAddress+p
                if rva+7+disp == target:
                    self.disasm(rva, 24)
            # Relative direct calls and jumps.
            for m in re.finditer(rb'[\xe8\xe9]', data):
                p = m.start()
                if p+5 <= len(data) and s.VirtualAddress+p+5+struct.unpack_from('<i',data,p+1)[0] == target:
                    self.disasm(s.VirtualAddress+p, 12)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--exe', default=DEFAULT_EXE)
    p.add_argument('--rtti', nargs='*')
    p.add_argument('--disasm', type=lambda x: int(x, 0))
    p.add_argument('--size', type=lambda x: int(x, 0), default=0x200)
    p.add_argument('--refs', type=lambda x: int(x, 0))
    p.add_argument('--function', type=lambda x: int(x, 0))
    args = p.parse_args()
    image = Image(args.exe)
    if args.rtti:
        print(json.dumps([r for name in args.rtti for r in image.rtti(name)], indent=2))
    if args.disasm is not None:
        image.disasm(args.disasm, args.size)
    if args.refs is not None:
        image.refs(args.refs)
    if args.function is not None:
        image.function(args.function)


if __name__ == '__main__':
    main()
