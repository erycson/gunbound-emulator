"""Async, fail-closed bridge to the optional operator-supplied Windows x86 worker.

Not registered in VALIDATORS: native qualification is still pending, so this
experimental binding can only be configured in observe mode.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import struct

from gunbound.game.ggauth50_codec import Codec
from gunbound.game.ggauth50_helper import DLL_SHA256, LIMIT

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DLL = 'vendor/gameguard/ggauth50.dll'


class HelperError(RuntimeError):
    pass


def validate_config(cfg):
    options = cfg.get('ggauth50') or {}
    if not isinstance(options, dict):
        raise ValueError('anticheat.ggauth50 must be a mapping')
    for key in ('python_x86', 'original_server', 'minimum_version'):
        if not options.get(key):
            raise ValueError(f'anticheat.ggauth50 requires {key}')
    if cfg.get('provider') != 'gameguard' or cfg.get('mode') != 'observe':
        raise ValueError('experimental ggauth50 binding supports gameguard observe only; required is unqualified')
    minimum = options['minimum_version']
    if isinstance(minimum, bool) or not isinstance(minimum, int) or not 2003010101 <= minimum <= 2010123199:
        raise ValueError('ggauth50 minimum_version must be an explicit supported integer')
    if not 0.1 <= float(options.get('timeout', 5)) <= 30:
        raise ValueError('ggauth50 timeout must be 0.1..30 seconds')
    return options


def project_dll(options):
    """Resolve operator-supplied DLLs relative to the project, never the cwd."""
    configured = Path(options.get('dll') or DEFAULT_DLL)
    path = (PROJECT_ROOT / configured).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError('ggauth50 DLL must be inside the server project (vendor/gameguard/ggauth50.dll)')
    if not path.is_file():
        raise FileNotFoundError(f'ggauth50 DLL missing: {path}. Copy the original DLL into the project before startup.')
    return path


class Helper:
    """One worker per GameServer; all sessions share its native global state."""
    def __init__(self, options):
        self.options = options
        self.process = None
        self.generation = None
        self.sequence = 0
        self.lock = asyncio.Lock()
        self.waiters = 0
        self.sessions = set()
        self.codec = None
        self.failed = False

    async def _frame(self, command, **values):
        self.sequence += 1
        req = dict(command=command, request_id=self.sequence, **values)
        if self.generation:
            req['generation'] = self.generation
        data = json.dumps(req, separators=(',', ':')).encode('utf-8')
        if len(data) > LIMIT:
            raise HelperError('request too large')
        self.process.stdin.write(struct.pack('<I', len(data)) + data)
        await self.process.stdin.drain()
        size, = struct.unpack('<I', await self.process.stdout.readexactly(4))
        if not 0 < size <= LIMIT:
            raise HelperError('response too large')
        res = json.loads((await self.process.stdout.readexactly(size)).decode('utf-8'))
        if not isinstance(res, dict) or res.get('request_id') != self.sequence or res.get('ok') is not True:
            raise HelperError('invalid response')
        generation = res.get('generation')
        if not isinstance(generation, str) or len(generation) != 32:
            raise HelperError('invalid generation')
        if self.generation and generation != self.generation:
            raise HelperError('worker generation changed')
        if not self.generation and command != 'hello':
            raise HelperError('handshake required')
        self.generation = generation
        return res

    async def _start(self):
        if self.failed:
            raise HelperError('worker invalidated; create a new server instance to retry')
        if self.process:
            return
        dll = project_dll(self.options)
        if hashlib.sha256(await asyncio.to_thread(dll.read_bytes)).hexdigest() != DLL_SHA256:
            raise HelperError('unsupported DLL SHA-256')
        self.codec = await asyncio.to_thread(Codec, self.options['original_server'])
        executable = str(Path(self.options['python_x86']).resolve(strict=True))
        self.process = await asyncio.create_subprocess_exec(
            executable, '-I', '-u', str(Path(__file__).with_name('ggauth50_helper.py')),
            '--dll', str(dll), '--minimum-version', str(self.options['minimum_version']),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=LIMIT+4,
            creationflags=0x08000000 if os.name == 'nt' else 0)  # CREATE_NO_WINDOW
        hello = await self._frame('hello')
        self._validate_hello(hello)

    def _validate_hello(self, hello):
        expected = dict(contract=1, protocol=0x10050, dll_sha256=DLL_SHA256,
                        architecture='x86', native=True, minimum_version=self.options['minimum_version'])
        if any(hello.get(k) != v for k, v in expected.items()):
            raise HelperError('unqualified worker handshake')

    async def request(self, command, **values):
        if self.waiters >= 64:
            raise HelperError('worker queue full')
        self.waiters += 1
        try:
            async with asyncio.timeout(float(self.options.get('timeout', 5))):
                async with self.lock:
                    await self._start()
                    return await self._frame(command, **values)
        except (Exception, asyncio.CancelledError) as exc:
            await self.close()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise HelperError('ggauth50 worker unavailable or invalid') from exc
        finally:
            self.waiters -= 1

    async def close(self):
        self.failed = True
        self.sessions.clear()
        process = self.process
        if process is not None:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()


class Validator:
    def __init__(self, helper):
        self.helper = helper
        self.session = None
        self.exchange = None
        self.internal = None
        self.closed = False

    async def query(self, exchange):
        from gunbound.game.anticheat import Query
        if self.closed or self.internal is not None:
            raise HelperError('session closed or already pending')
        if self.session is None:
            res = await self.helper.request('create_session')
            self.session = res['session_id']
            if not isinstance(self.session, str) or len(self.session) != 32:
                raise HelperError('invalid session id')
            self.helper.sessions.add(self.session)
        res = await self.helper.request('query', session_id=self.session)
        if res.get('code') != 0:
            raise HelperError('native query rejected')
        internal = bytes.fromhex(res['internal'])
        number = res['exchange_id']
        if len(internal) != 16 or type(number) is not int or number <= (self.exchange or 0):
            raise HelperError('invalid query')
        self.internal, self.exchange = internal, number
        return Query(internal, self.helper.codec.encode_query(internal))

    async def check(self, exchange, internal, answer):
        if self.closed or self.internal is None or internal != self.internal or len(answer) != 16:
            return False
        self.internal = None  # no retries/replay, even when the worker rejects
        res = await self.helper.request('check', session_id=self.session, exchange_id=self.exchange,
                                        answer=self.helper.codec.decode_answer(answer).hex())
        return res.get('code') == 0 and res.get('accepted') is True

    async def close(self):
        if self.closed:
            return
        self.closed = True
        if self.session and not self.helper.failed:
            try:
                await self.helper.request('close_session', session_id=self.session)
            finally:
                self.helper.sessions.discard(self.session)


def from_config(server, cfg):
    validate_config(cfg)
    helper = getattr(server, '_ggauth50_helper', None)
    if helper is None or helper.failed:
        raise HelperError('ggauth50 worker is not initialized; restart the GameServer after fixing startup')
    return Validator(helper)


async def initialize(server, cfg):
    """Load/handshake before opening the listener; startup must fail on error."""
    options = dict(validate_config(cfg))
    # Keep the missing/outside-path error explicit, before worker error wrapping.
    options['dll'] = str(project_dll(options))
    helper = Helper(options)
    try:
        await helper.request('hello')
    except BaseException:
        await helper.close()
        raise
    server._ggauth50_helper = helper
