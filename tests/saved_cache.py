"""Synthetic serialized-cache tests; no real save/game/network access."""
import hashlib
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from read_saved_cache import entries,cache_region,NET_SIZE
from watch_saved_cache import fresh_records


def message(size=606,sender=42):
    b=bytearray(size);offset=size-602
    b[offset+0x190:offset+0x190+12]=b'PRIVATE_NAME'
    struct.pack_into('<I',b,offset+0x1b4,sender)
    struct.pack_into('<II3ff8H',b,offset+0x1c0,0x1f030000,31030,1.,2.,3.,0.,10000,255,30008,0,0,0,4,3)
    struct.pack_into('<I',b,offset+0x1f8,3103001)
    return struct.pack('<II',1,size)+b+bytes(-size%4)+struct.pack('<II',65535,0)


class SavedCache(unittest.TestCase):
    def test_alignment_variants_match_and_identity_excluded(self):
        a,_=entries(message(602));b,_=entries(message(606));self.assertEqual(a,b)
        self.assertEqual(a[0]['good']+a[0]['poor'],7)
        self.assertNotIn('PRIVATE',str(a))
    def test_local_replay_and_truncation(self):
        self.assertEqual(entries(message(sender=0x7e000001)),([],1))
        with self.assertRaises(ValueError):entries(message()[:-1])
    def test_requires_complete_chunk_chain_and_padding(self):
        sub=struct.pack('<II',65535,0);chain=b''
        for k,v in [(2,0),(5,0),(6,2),(8,0),(9,0),(7,1)]:
            body=message() if k==6 else sub
            chain+=struct.pack('<HHI',k,v,len(body))+body
        region=struct.pack('<I',2)+chain+struct.pack('<HHI',65535,0,0)
        region+=bytes(NET_SIZE-len(region))
        self.assertEqual(cache_region(region),message())
        self.assertIsNone(cache_region(region[:-1]+b'X'))
    def test_historical_and_rating_only_changes_are_excluded(self):
        records,_=entries(message());new=[dict(records[0],good=20)]
        self.assertEqual(fresh_records({'records':records},{'records':new}),{})
        new[0]['position']=[20.,2.,3.]
        self.assertEqual(len(fresh_records({'records':records},{'records':new})),1)


if __name__=='__main__':unittest.main()
