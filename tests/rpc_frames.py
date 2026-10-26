import asyncio
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/protocol_pilot'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from rpc_frames import await_response,CandidateCheckpoint
from capture_client_cache import fingerprint

class FakeTransport:
    def __init__(self,frames):self.frames=iter(frames)
    async def receive(self):return next(self.frames)

class RoutingTests(unittest.TestCase):
    def test_notification_contents_not_retained_and_no_outbound_api(self):
        response=struct.pack('<BIBI',5,3,1,18)
        frames=[b'\x06\x00PRIVATE-PLAYER-DATA',b'\x07\x64',response]
        events=[]
        with self.assertRaises(ValueError):asyncio.run(await_response(FakeTransport(frames),3,18,events))
        self.assertEqual(events[0]['frame'],'unverified_push_rejected')
        self.assertNotIn('PRIVATE',str(events))
        self.assertEqual(asyncio.run(await_response(FakeTransport([b'\x07\x64',response]),3,18,[])),response)
    def test_only_known_completed_sequences_can_be_skipped(self):
        old=struct.pack('<BIBI',5,1,1,0);good=struct.pack('<BIBI',5,2,1,18)
        self.assertEqual(asyncio.run(await_response(FakeTransport([old,good]),2,18,[],completed={1})),good)
        with self.assertRaises(ValueError):asyncio.run(await_response(FakeTransport([old]),2,18,[]))
    def test_unexpected_and_unbounded_frames_stop(self):
        with self.assertRaises(ValueError):asyncio.run(await_response(FakeTransport([b'\x08secret']),2,18,[]))
        with self.assertRaises(RuntimeError):asyncio.run(await_response(FakeTransport([b'\x07\x64']*17),2,18,[]))
    def test_partial_data_survives_later_failure_and_identity_rejected(self):
        r=dict(map=0x1f030000,area=3103001,secondary_area=31030,position=[1.,2.,3.],
            yaw=0.,template1=10001,word1=30008,conjunction=0,template2=0,word2=0,good=1,poor=0)
        r=dict(candidate_key=fingerprint(r),**r)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'candidate.json';cp=CandidateCheckpoint(p)
            cp.save([r],[{'target':'first'}])
            cp.save([r],[{'target':'first'}],finished=True,reason='later transport failure')
            self.assertEqual(json.loads(p.read_text())['records'],[r])
            before=p.read_bytes()
            with self.assertRaises(ValueError):cp.save([dict(r,player_id=123)],[])
            self.assertEqual(before,p.read_bytes())

if __name__=='__main__':unittest.main()
