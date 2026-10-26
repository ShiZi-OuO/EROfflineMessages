"""Exact-host TLS/WSS transport for the explicitly authorized small pilot.

No game process access, EAC integration, certificate overrides or system route
changes. The interface index applies only to this process's socket.
"""
import asyncio
import os
import socket
import struct
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'build/research/protocol-python-libs'))
from nacl.bindings import (crypto_box,crypto_box_open,crypto_kx_keypair,
    crypto_kx_client_session_keys,crypto_secretbox,crypto_secretbox_open)
from websockets.asyncio.client import connect

HOST='gr-prod-steam.fromsoftware-game.net'


class SessionTransport:
    def __init__(self,ip,interface,materials):
        self.ip=ip;self.interface=interface;self.materials=Path(materials)
        self.socket=None;self.ws=None
    async def open(self):
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.socket.settimeout(10)
        self.socket.setsockopt(socket.IPPROTO_IP,31,struct.pack('!I',self.interface))
        self.socket.connect((self.ip,10901));self.socket.setblocking(False)
        self.ws=await connect('wss://'+HOST+':10901/',sock=self.socket,proxy=None,
            open_timeout=15,close_timeout=3,max_size=16*1024*1024,ping_interval=None)
        await self.ws.send(b'\x00\x00\x01\x00')
        raw=await asyncio.wait_for(self.ws.recv(),10)
        if not isinstance(raw,bytes) or len(raw)!=120:raise ValueError('Unexpected bootstrap frame')
        server_key=(self.materials/'server_public_key').read_bytes()
        client_key=(self.materials/'client_secret_key').read_bytes()
        plain=crypto_box_open(raw[24:],raw[:24],server_key,client_key)
        if len(plain)!=80:raise ValueError('Unexpected bootstrap plaintext')
        client_public,client_private=crypto_kx_keypair()
        self.rx,self.tx=crypto_kx_client_session_keys(client_public,client_private,plain[:32])
        self.recv_nonce=plain[32:56];self.send_nonce=plain[56:80]
        nonce=os.urandom(24)
        await self.ws.send(nonce+crypto_box(client_public,nonce,server_key,client_key))
    @staticmethod
    def increment(nonce):return ((int.from_bytes(nonce,'little')+1)%(1<<192)).to_bytes(24,'little')
    async def send(self,data):
        await self.ws.send(crypto_secretbox(data,self.send_nonce,self.tx))
        self.send_nonce=self.increment(self.send_nonce)
    async def receive(self):
        raw=await asyncio.wait_for(self.ws.recv(),15)
        if not isinstance(raw,bytes):raise ValueError('Expected encrypted binary frame')
        plain=crypto_secretbox_open(raw,self.recv_nonce,self.rx)
        self.recv_nonce=self.increment(self.recv_nonce)
        return plain
    async def close(self):
        if self.ws:await self.ws.close()
        if self.socket:self.socket.close()
