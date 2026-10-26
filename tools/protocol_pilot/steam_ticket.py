"""Standalone Steam encrypted-app-ticket acquisition, no game process access.

Uses the user's installed, unmodified steam_api64.dll and logged-in Steam.
Ticket bytes stay in memory; this module never prints/persists account data.
Valve APIs: ISteamUser::RequestEncryptedAppTicket/GetEncryptedAppTicket and
ISteamUtils::IsAPICallCompleted/GetAPICallResult.
"""
import ctypes as c
import os
import time
from pathlib import Path


class SteamTicket:
    def __init__(self, dll_path):
        os.environ['SteamAppId'] = '1245620'
        os.environ['SteamGameId'] = '1245620'
        self.api = c.CDLL(str(Path(dll_path).resolve()))
        def bind(name, result, args):
            f = getattr(self.api, name); f.restype = result; f.argtypes = args
            return f
        self.init = bind('SteamAPI_InitSafe', c.c_bool, [])
        self.shutdown = bind('SteamAPI_Shutdown', None, [])
        self.run = bind('SteamAPI_RunCallbacks', None, [])
        self.user = bind('SteamAPI_SteamUser_v021', c.c_void_p, [])
        self.utils = bind('SteamAPI_SteamUtils_v010', c.c_void_p, [])
        self.request = bind('SteamAPI_ISteamUser_RequestEncryptedAppTicket', c.c_uint64,
                            [c.c_void_p, c.c_void_p, c.c_int])
        self.complete = bind('SteamAPI_ISteamUtils_IsAPICallCompleted', c.c_bool,
                             [c.c_void_p, c.c_uint64, c.POINTER(c.c_bool)])
        self.result = bind('SteamAPI_ISteamUtils_GetAPICallResult', c.c_bool,
                           [c.c_void_p, c.c_uint64, c.c_void_p, c.c_int, c.c_int,
                            c.POINTER(c.c_bool)])
        self.get = bind('SteamAPI_ISteamUser_GetEncryptedAppTicket', c.c_bool,
                        [c.c_void_p, c.c_void_p, c.c_int, c.POINTER(c.c_uint32)])
        self.started = False

    def acquire(self, userdata=b'', timeout=25):
        if self.started:
            raise RuntimeError('Only one ticket request per instance')
        if not self.init():
            raise RuntimeError('Steam API initialization failed')
        self.started = True
        user, utils = self.user(), self.utils()
        if not user or not utils:
            raise RuntimeError('Required Steam interface unavailable')
        data = c.create_string_buffer(userdata) if userdata else None
        handle = self.request(user, data, len(userdata))
        if not handle:
            raise RuntimeError('Encrypted ticket request returned no call handle')
        failed = c.c_bool()
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            self.run()
            if self.complete(utils, handle, c.byref(failed)):
                if failed.value:
                    raise RuntimeError('Steam ticket API call failed')
                status = c.c_int()
                if not self.result(utils, handle, c.byref(status), c.sizeof(status),
                                   154, c.byref(failed)) or failed.value:
                    raise RuntimeError('Steam ticket response unavailable')
                if status.value != 1:
                    raise RuntimeError(f'Steam encrypted ticket EResult={status.value}')
                buffer = c.create_string_buffer(4096)
                size = c.c_uint32()
                if not self.get(user, buffer, len(buffer), c.byref(size)) or not 0 < size.value <= len(buffer):
                    raise RuntimeError('Steam encrypted ticket retrieval failed')
                return bytes(buffer.raw[:size.value])
            time.sleep(.05)
        raise TimeoutError('Steam encrypted ticket callback deadline')

    def close(self):
        if self.started:
            self.shutdown()
            self.started = False
