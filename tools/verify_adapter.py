"""Verify EVERY runtime function signature against the exact on-disk game image."""
import hashlib
import re
from pathlib import Path
from research_pe import Image,DEFAULT_EXE
root=Path(__file__).resolve().parent.parent
if hashlib.sha256(Path(DEFAULT_EXE).read_bytes()).hexdigest()!='f9118fea2cfd8fa3901e8060bfadb1552cb2471771ded8a5b662c4e298ffb328':raise RuntimeError('Unsupported image')
image=Image(DEFAULT_EXE)
source=(root/'src'/'NativeReplay.cpp').read_text(encoding='utf-8')
signatures=re.findall(r'Signature\((0x[0-9a-f]+),\{([^}]+)\}',source)
if len(signatures)!=6:raise RuntimeError('Expected six critical entry signatures')
for rva,values in signatures:
    expected=bytes(int(x.strip(),16) for x in values.split(','))
    actual=image.bytes(int(rva,16),len(expected))
    if actual!=expected:raise RuntimeError(f'Signature mismatch at {rva}: {actual.hex()} != {expected.hex()}')
    print(f'PASS {rva}: {len(expected)} exact entry bytes')
