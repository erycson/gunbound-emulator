"""No vendor binary is executed by this suite. Native tests are a separate operator gate."""
import asyncio
import ctypes as C
import io
import struct
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from gunbound.game.ggauth50 import Helper, HelperError, Validator, validate_config
from gunbound.game.ggauth50_helper import Block, Native, Session, Version, Worker, read_frame, write_frame, serve


class FakeNative:
    def __init__(self):
        self.check_calls = 0
        self.ticks = 0

    def query(self, s):
        if s.flags.value & 2:
            return 11
        s.flags.value |= 3
        s.query.words[:] = [0 if not s.version.raw else 346, 0, 0, 0x10050]
        return 0

    def check(self, s):
        self.check_calls += 1
        s.flags.value &= ~2
        return 0 if s.answer.words[3] == 0x12345678 else 13

    def update(self):
        self.ticks += 1


def answer(version=2009010101, correct=True, protocol=0x10050):
    return struct.pack('<4I', protocol, 0, version, 0x12345678 if correct else 0).hex()


class WorkerTest(unittest.TestCase):
    def setUp(self):
        self.native = FakeNative()
        self.worker = Worker(self.native, 2003010101)

    def create(self):
        return self.worker.dispatch({'command': 'create_session'})['session_id']

    def call(self, sid, cmd, **kw):
        return self.worker.dispatch(dict(command=cmd, session_id=sid, generation=self.worker.generation, **kw))

    def test_abi_layout(self):
        self.assertEqual((C.sizeof(Version), C.sizeof(Block)), (12, 16))
        self.assertEqual([getattr(Version, field).offset for field in ('raw', 'year', 'month', 'day', 'revision')],
                         [0, 4, 6, 8, 10])

    def test_initial_followup_and_replay(self):
        sid = self.create()
        q = self.call(sid, 'query')
        self.assertEqual(q['internal'], '00' * 12 + '50000100')
        with self.assertRaises(ValueError):
            self.call(sid, 'query')
        self.assertTrue(self.call(sid, 'check', exchange_id=1, answer=answer())['accepted'])
        self.assertEqual(self.worker.sessions[sid].version.raw, 2009010101)
        self.assertEqual(self.worker.sessions[sid].flags.value, 1)
        with self.assertRaises(ValueError):
            self.call(sid, 'check', exchange_id=1, answer=answer())
        self.assertEqual(self.native.check_calls, 1)
        q = self.call(sid, 'query')
        self.assertEqual(q['exchange_id'], 2)
        self.assertEqual(bytes.fromhex(q['internal'])[:4], struct.pack('<I', 346))

    def test_no_pending_cannot_call_native(self):
        sid = self.create()
        with self.assertRaises(ValueError):
            self.call(sid, 'check', exchange_id=0, answer=answer())
        self.assertEqual(self.native.check_calls, 0)

    def test_sessions_interleaved_and_old_exchange(self):
        a, b = self.create(), self.create()
        self.call(a, 'query')
        self.call(b, 'query')
        self.call(b, 'check', exchange_id=1, answer=answer(version=2008010101))
        self.assertTrue(self.worker.sessions[a].pending)
        self.assertEqual(self.worker.sessions[a].version.raw, 0)
        with self.assertRaises(ValueError):
            self.call(a, 'check', exchange_id=2, answer=answer())
        self.call(a, 'check', exchange_id=1, answer=answer())
        self.assertEqual(self.worker.sessions[b].version.raw, 2008010101)

    def test_invalid_answer_invalidates_session(self):
        sid = self.create()
        self.call(sid, 'query')
        self.assertEqual(self.call(sid, 'check', exchange_id=1, answer=answer(correct=False))['code'], 13)
        self.assertNotIn(sid, self.worker.sessions)

    def test_version_bounds_and_unsupported_protocol(self):
        for version, protocol in [(2002010101, 0x10050), (2011010101, 0x10050),
                                  (2009000101, 0x10050), (2009010001, 0x10050),
                                  (2009010100, 0x10050), (2009010101, 0x10051)]:
            with self.subTest(version=version, protocol=protocol):
                sid = self.create()
                self.call(sid, 'query')
                self.assertFalse(self.call(sid, 'check', exchange_id=1,
                                          answer=answer(version=version, protocol=protocol))['accepted'])
                self.assertNotIn(sid, self.worker.sessions)
        self.assertEqual(self.native.check_calls, 0)

    def test_explicit_minimum(self):
        self.worker.minimum_version = 2009010201
        sid = self.create()
        self.call(sid, 'query')
        self.assertFalse(self.call(sid, 'check', exchange_id=1, answer=answer())['accepted'])

    def test_old_generation_and_close(self):
        sid = self.create()
        with self.assertRaises(ValueError):
            self.worker.dispatch(dict(command='query', session_id=sid, generation='b' * 32))
        self.call(sid, 'close_session')
        self.assertEqual(self.worker.sessions, {})

    def test_native_refuses_non_x86_runtime(self):
        if sys.platform != 'win32' or C.sizeof(C.c_void_p) != 4:
            with self.assertRaisesRegex(RuntimeError, 'x86'):
                Native('missing.dll')

    def test_framing_and_bounds(self):
        target = io.BytesIO()
        write_frame(target, {'command': 'hello'})
        self.assertEqual(read_frame(io.BytesIO(target.getvalue())), {'command': 'hello'})
        for data in (struct.pack('<I', 0), struct.pack('<I', 4097), struct.pack('<I', 2) + b'[]'):
            with self.assertRaises(ValueError):
                read_frame(io.BytesIO(data))
        with self.assertRaises(EOFError):
            read_frame(io.BytesIO(struct.pack('<I', 10) + b'{}'))

    def test_timer_runs_on_calling_thread(self):
        calls = []
        class NativeTimer(FakeNative):
            def update(self):
                calls.append(threading.get_ident())
        # The reader blocks briefly; serve's main thread must dispatch the timer.
        class SlowEOF:
            def read(self, size):
                time.sleep(0.055)
                return b''
        native = NativeTimer()
        serve(Worker(native, 2003010101), SlowEOF(), io.BytesIO(), timer_seconds=0.01)
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(set(calls), {threading.get_ident()})


class IdentityCodec:
    def encode_query(self, body):
        return body

    def decode_answer(self, body):
        return body


class FakeHelper(Helper):
    """Launches an actual subprocess/pipe but never loads a vendor DLL."""
    def __init__(self, mode='normal', timeout=0.8):
        super().__init__({'timeout': timeout, 'minimum_version': 2003010101})
        self.mode = mode

    async def _start(self):
        if self.failed:
            raise HelperError('invalidated')
        if not self.process:
            self.codec = IdentityCodec()
            fixture = Path(__file__).with_name('fixtures') / 'ggauth50_fake_worker.py'
            self.process = await asyncio.create_subprocess_exec(sys.executable, '-u', str(fixture), self.mode,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            self._validate_hello(await self._frame('hello'))


class BridgeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.helpers = []

    def helper(self, *args, **kwargs):
        helper = FakeHelper(*args, **kwargs)
        self.helpers.append(helper)
        return helper

    async def asyncTearDown(self):
        for helper in self.helpers:
            await helper.close()
            if helper.process:
                self.assertIsNotNone(helper.process.returncode)

    async def test_roundtrip_and_replay(self):
        helper = self.helper()
        validator = Validator(helper)
        query = await validator.query(None)
        self.assertEqual(len(query.internal), 16)
        self.assertEqual(query.wire, query.internal)
        with self.assertRaises(HelperError):
            await validator.query(None)
        self.assertFalse(await validator.check(None, b'wrong', bytes(16)))
        self.assertTrue(await validator.check(None, query.internal, bytes(16)))
        self.assertFalse(await validator.check(None, query.internal, bytes(16)))
        await validator.close()
        self.assertEqual(helper.sessions, set())

    async def test_transport_failures_invalidate_worker(self):
        for mode in ('crash', 'hang', 'oversize', 'truncated', 'bad_id', 'restart'):
            with self.subTest(mode=mode):
                helper = self.helper(mode)
                with self.assertRaises(HelperError):
                    await helper.request('create_session')
                self.assertTrue(helper.failed)
                self.assertIsNotNone(helper.process.returncode)
                with self.assertRaises(HelperError):
                    await helper.request('create_session')

    async def test_cancel_kills_inflight_worker(self):
        helper = self.helper('hang', timeout=10)
        task = asyncio.create_task(helper.request('create_session'))
        while helper.generation is None:
            await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(helper.failed)
        self.assertIsNotNone(helper.process.returncode)

    async def test_serialized_concurrent_requests(self):
        helper = self.helper()
        results = await asyncio.gather(*(helper.request('create_session') for _ in range(20)))
        self.assertEqual(len({row['request_id'] for row in results}), 20)

    async def test_queue_limit(self):
        helper = self.helper()
        helper.waiters = 64
        with self.assertRaisesRegex(HelperError, 'queue full'):
            await helper.request('create_session')

    async def test_wrong_dll_hash_never_spawns_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            dll = Path(folder) / 'not-the-vendor.dll'
            dll.write_bytes(b'not an executable')
            helper = Helper({'dll': str(dll), 'timeout': 1})
            with self.assertRaises(HelperError):
                await helper.request('create_session')
            self.assertTrue(helper.failed)
            self.assertIsNone(helper.process)

    def test_codec_refuses_wrong_server_hash(self):
        from gunbound.game.ggauth50_codec import Codec
        with tempfile.TemporaryDirectory() as folder:
            server = Path(folder) / 'server.exe'
            server.write_bytes(b'not the reference server')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                Codec(server)

    def test_handshake_and_required_gate(self):
        cfg = dict(provider='gameguard', mode='observe', ggauth50=dict(python_x86='py32.exe', dll='ggauth50.dll',
                   original_server='GunBoundServ3.exe', minimum_version=2003010101))
        self.assertEqual(validate_config(cfg)['minimum_version'], 2003010101)
        for mode in ('required', 'off', 'capture'):
            with self.assertRaises(ValueError):
                validate_config(dict(cfg, mode=mode))
        with self.assertRaises(ValueError):
            validate_config(dict(cfg, ggauth50={}))
        helper = FakeHelper()
        with self.assertRaises(HelperError):
            helper._validate_hello(dict(contract=1))


class IntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_async_bridge_observe_sends_success_only_after_check(self):
        from tests.test_anticheat import player, cmds
        from gunbound.game.anticheat import AntiCheat
        helper = FakeHelper()
        conn = player()
        ac = AntiCheat(conn, 'gameguard', 'observe', Validator(helper))
        ac.start()
        try:
            for _ in range(100):
                if ac.pending:
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(cmds(conn), [0x1015])
            await ac.on_answer(0x1016, bytes(16))
            self.assertEqual(cmds(conn), [0x1015, 0x1017])
            await ac.on_answer(0x1016, bytes(16))
            self.assertEqual(cmds(conn).count(0x1017), 1)
            self.assertFalse(conn.closing)
        finally:
            ac.close()
            await asyncio.sleep(0.02)
            await helper.close()

    async def test_worker_failure_never_sends_auth_success(self):
        from tests.test_anticheat import player, cmds
        from gunbound.game.anticheat import AntiCheat
        helper = FakeHelper('crash')
        conn = player()
        ac = AntiCheat(conn, 'gameguard', 'observe', Validator(helper))
        ac.start()
        try:
            for _ in range(100):
                if helper.failed:
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(helper.failed)
            self.assertEqual(cmds(conn), [])
        finally:
            ac.close()
            await asyncio.sleep(0.02)
            await helper.close()


if __name__ == '__main__':
    unittest.main()
