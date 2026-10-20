"""Private stdio worker. Run ONLY with Windows Python x86; never import a vendor DLL in the server.

Contract 1 uses 4-byte little-endian lengths and JSON, not the original GameGuard protocol.
The reader thread only reads IPC. All native calls, including the 300-second timer, run
on the main thread so the vendor CRT's TLS/RNG remains on its initializing thread.
"""
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import queue
import struct
import sys
import threading
import time
import uuid

DLL_SHA256 = 'a8d81e5276ac502cfa41ffd5142deeaaca102537409d141bf1e628c2daee5257'
LIMIT = 4096


class Version(C.Structure):
    _fields_ = [('raw', C.c_uint32), ('year', C.c_uint16), ('month', C.c_uint16),
                ('day', C.c_uint16), ('revision', C.c_uint16)]


class Block(C.Structure):
    _fields_ = [('words', C.c_uint32 * 4)]


assert C.sizeof(Version) == 12 and C.sizeof(Block) == 16


def block(value: str) -> Block:
    data = bytes.fromhex(value)
    if len(data) != 16:
        raise ValueError('block_size')
    return Block.from_buffer_copy(data)


def read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        part = stream.read(size - len(data))
        if not part:
            raise EOFError
        data.extend(part)
    return bytes(data)


def read_frame(stream):
    size, = struct.unpack('<I', read_exact(stream, 4))
    if not 0 < size <= LIMIT:
        raise ValueError('frame_size')
    value = json.loads(read_exact(stream, size).decode('utf-8'))
    if not isinstance(value, dict):
        raise ValueError('frame_type')
    return value


def write_frame(stream, value):
    data = json.dumps(value, separators=(',', ':')).encode('utf-8')
    if len(data) > LIMIT:
        raise ValueError('frame_size')
    stream.write(struct.pack('<I', len(data)) + data)
    stream.flush()


class Native:
    def __init__(self, path):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 4:
            raise RuntimeError('Windows Python x86 required')
        path = Path(path).resolve(strict=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != DLL_SHA256:
            raise ValueError('unsupported_dll_sha256')
        # LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32.
        # Only this approved DLL directory and System32 may supply dependencies.
        self.dll = C.CDLL(str(path), winmode=0x100 | 0x800)
        signatures = {
            'PrtcGetVersion': [C.c_uint32], 'PrtcUpdateTimer': [],
            'PrtcGetAuthQuery': [C.c_uint32, C.POINTER(Version), C.POINTER(C.c_uint32),
                                 C.POINTER(Block), C.POINTER(Block)],
            'PrtcCheckAuthAnswer': [C.c_uint32, C.POINTER(Version), C.POINTER(C.c_uint32),
                                    C.POINTER(Block), C.POINTER(Block)],
            'PrtcEncryptQuery': [C.POINTER(Block)], 'PrtcDecryptAnswer': [C.POINTER(Block)],
        }
        for name, args in signatures.items():
            fn = getattr(self.dll, name)
            fn.argtypes, fn.restype = args, C.c_uint32
        if self.dll.PrtcGetVersion(1) != 0x10050:
            raise RuntimeError('protocol_mismatch')

    def update(self):
        if self.dll.PrtcUpdateTimer() != 0:
            raise RuntimeError('timer_failed')

    def query(self, session):
        return self.dll.PrtcGetAuthQuery(0, C.byref(session.version), C.byref(session.flags),
                                        C.byref(session.query), C.byref(session.answer))

    def check(self, session):
        return self.dll.PrtcCheckAuthAnswer(0, C.byref(session.version), C.byref(session.flags),
                                           C.byref(session.query), C.byref(session.answer))


class Session:
    def __init__(self):
        self.version, self.flags = Version(), C.c_uint32()
        self.query, self.answer = Block(), Block()
        self.pending, self.exchange = False, 0


class Worker:
    def __init__(self, native, minimum_version):
        self.native, self.minimum_version = native, minimum_version
        self.generation = uuid.uuid4().hex
        self.sessions = {}
        self.timer_updates = 0

    def dispatch(self, req):
        cmd = req['command']
        if cmd == 'hello':
            return dict(contract=1, protocol=0x10050, dll_sha256=DLL_SHA256,
                        architecture='x86', native=True, minimum_version=self.minimum_version,
                        timer_updates=self.timer_updates)
        if cmd == 'create_session':
            if len(self.sessions) >= 1024:
                raise ValueError('session_limit')
            sid = uuid.uuid4().hex
            self.sessions[sid] = Session()
            return dict(session_id=sid)
        if req.get('generation') != self.generation:
            raise ValueError('stale_generation')
        sid = req['session_id']
        if cmd == 'close_session':
            self.sessions.pop(sid, None)
            return {}
        s = self.sessions[sid]
        if cmd == 'query':
            if s.pending:
                raise ValueError('already_pending')
            rc = self.native.query(s)
            if rc:
                self.sessions.pop(sid)
                return dict(code=rc)
            if not s.flags.value & 2:
                raise RuntimeError('native_missing_pending')
            s.pending = True
            s.exchange += 1
            # DLL50 transforms are confirmed no-ops for this exact hash. Keep the
            # native query unchanged; the parent applies the S2 wire codec.
            return dict(code=0, exchange_id=s.exchange, internal=bytes(s.query).hex())
        if cmd != 'check' or not s.pending or req['exchange_id'] != s.exchange:
            raise ValueError('no_matching_pending')
        s.pending = False  # invalid responses consume the pending exchange too
        s.answer = block(req['answer'])
        if s.answer.words[0] != 0x10050:
            self.sessions.pop(sid)
            return dict(code=12, accepted=False)
        if s.query.words[0] == 0:
            raw = int(s.answer.words[2])
            year, month, day, revision = raw // 1000000, raw // 10000 % 100, raw // 100 % 100, raw % 100
            if not (2003 <= year <= 2010 and 1 <= month <= 12 and 1 <= day <= 31 and
                    1 <= revision <= 99 and raw >= self.minimum_version):
                self.sessions.pop(sid)
                return dict(code=12, accepted=False)
            s.version = Version(raw, year, month, day, revision)
        rc = self.native.check(s)
        if rc:
            self.sessions.pop(sid)
        return dict(code=rc, accepted=rc == 0)


def serve(worker, source, dest, clock=time.monotonic, timer_seconds=300):
    incoming = queue.Queue(maxsize=8)

    def reader():
        try:
            while True:
                incoming.put(read_frame(source))
        except (EOFError, ValueError, UnicodeError):
            incoming.put(None)

    threading.Thread(target=reader, daemon=True).start()
    next_tick = clock() + timer_seconds
    while True:
        if clock() >= next_tick:
            worker.native.update()  # same native thread, never a Windows timer callback
            worker.timer_updates += 1
            next_tick = clock() + timer_seconds
        try:
            req = incoming.get(timeout=max(0.001, next_tick - clock()))
        except queue.Empty:
            continue
        if req is None:
            return
        result = dict(request_id=req.get('request_id'), generation=worker.generation)
        try:
            result.update(worker.dispatch(req), ok=True)
        except (KeyError, ValueError):
            # No raw input, auth bodies, paths, or native exception text on stderr/stdout.
            result.update(ok=False, error='invalid_request')
        write_frame(dest, result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dll', required=True)
    parser.add_argument('--minimum-version', required=True, type=int)
    args = parser.parse_args()
    if not 2003010101 <= args.minimum_version <= 2010123199:
        parser.error('minimum-version outside supported year interval')
    native = Native(args.dll)
    serve(Worker(native, args.minimum_version), sys.stdin.buffer, sys.stdout.buffer)


if __name__ == '__main__':
    main()
