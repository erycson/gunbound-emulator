"""Anti-hack (gunbound/game/anticheat.py): modos off/observe/capture/required, sem sucesso fixo.
O validador falso existe só aqui; nenhuma configuração consegue escolhê-lo. python -m unittest tests.test_anticheat"""
import asyncio
import hashlib
import json
import os
import struct
import tempfile
import unittest
from gunbound.game import anticheat
from gunbound.game.anticheat import AntiCheat, PROFILES, Query
from tests.test_gm import conn


class FakeValidator:
    """Pergunta no fio = interna invertida; resposta certa = sha256(pergunta interna)[:16]."""
    def __init__(self):
        self.n = 0

    def query(self, ex):
        self.n += 1
        internal = struct.pack('<I', self.n).ljust(ex.challenge_len, b'q')
        return Query(internal, internal[::-1])

    def check(self, ex, internal, answer):
        return answer == hashlib.sha256(internal).digest()[:16]


def right(wire):
    return hashlib.sha256(wire[::-1]).digest()[:16]   # o check recebe a pergunta interna, não a do fio


def player():
    c = conn('u')
    c.server.config = {}
    return c


def cmds(c):
    return [struct.unpack_from('<H', b)[0] for b in c.sent]


class SettingsTest(unittest.TestCase):
    def test_defaults_and_yaml_off(self):
        self.assertEqual(anticheat.settings({}), ('none', 'off'))
        self.assertEqual(anticheat.settings({'anticheat': {'provider': 'gameguard', 'mode': False}}), ('gameguard', 'off'))
        self.assertEqual(anticheat.settings({'anticheat': {'provider': 'gameguard', 'mode': 'observe'}}), ('gameguard', 'observe'))

    def test_required_without_validator_refuses(self):
        for provider in ('gameguard', 'hackshield'):
            with self.assertRaises(ValueError):
                anticheat.settings({'anticheat': {'provider': provider, 'mode': 'required'}})
        with self.assertRaises(ValueError):
            anticheat.settings({'anticheat': {'provider': 'xigncode', 'mode': 'observe'}})
        self.assertEqual(anticheat.VALIDATORS, {})  # nenhum validador de produção registrado


class AntiCheatTest(unittest.IsolatedAsyncioTestCase):
    async def settle(self):
        for _ in range(3):
            await asyncio.sleep(0)

    def session(self, mode='required', validator=None, **kw):
        c = player()
        ac = AntiCheat(c, 'gameguard', mode, validator, **kw)
        c.anticheat = ac
        return c, ac

    async def test_off_sends_nothing_and_never_answers(self):
        c, ac = self.session('off', FakeValidator())
        ac.start()
        await ac.on_answer(0x1016, b'\x00' * 16)
        await self.settle()
        self.assertEqual(c.sent, [])  # nem 0x1015 nem 0x1017

    async def test_observe_without_validator_logs_only(self):
        c, ac = self.session('observe', None)
        ac.start()
        ac.pending[0x1016] = (Query(b'', b'x' * 16), 0.0)   # pergunta vinda de fora (ex.: captura); sem validador não há veredito
        await ac.on_answer(0x1016, b'\x00' * 16)
        await self.settle()
        self.assertNotIn(0x1017, cmds(c))
        self.assertFalse(c.closing)

    async def test_valid_answer_then_replay(self):
        c, ac = self.session(validator=FakeValidator())
        ac.start()
        await self.settle()
        query = c.sent[0][2:]
        self.assertEqual((cmds(c), len(query)), ([0x1015], 16))
        await ac.on_answer(0x1016, right(query))
        self.assertEqual(c.last(0x1017)[2:], b'\x00\x00')
        await ac.on_answer(0x1016, right(query))   # repetida: não há pergunta pendente
        self.assertTrue(c.closing)
        self.assertEqual(cmds(c).count(0x1017), 1)
        ac.close()

    async def test_altered_and_truncated_disconnect(self):
        for answer in (lambda q: bytes([right(q)[0] ^ 1]) + right(q)[1:], lambda q: right(q)[:8]):
            c, ac = self.session(validator=FakeValidator())
            ac.start()
            await self.settle()
            await ac.on_answer(0x1016, answer(c.sent[0][2:]))
            self.assertTrue(c.closing)
            self.assertNotIn(0x1017, cmds(c))
            ac.close()

    async def test_observe_with_validator_never_disconnects(self):
        c, ac = self.session('observe', FakeValidator())
        ac.start()
        await self.settle()
        await ac.on_answer(0x1016, b'\x00' * 16)
        self.assertFalse(c.closing)
        self.assertNotIn(0x1017, cmds(c))
        ac.close()

    async def test_timeout_and_disconnect_cancels_timers(self):
        c, ac = self.session(validator=FakeValidator(), deadline=0.02)
        ac.start()
        await asyncio.sleep(0.05)
        await self.settle()
        self.assertTrue(c.closing)
        c2, ac2 = self.session(validator=FakeValidator(), deadline=0.02)
        ac2.start()
        ac2.close()                     # desconectou antes do prazo
        await asyncio.sleep(0.05)
        self.assertFalse(c2.closing)
        self.assertEqual(ac2.timers, [])

    async def test_two_sessions_isolated(self):
        v = FakeValidator()
        a, aca = self.session(validator=v)
        b, acb = self.session(validator=v)
        aca.start(), acb.start()
        await self.settle()
        await acb.on_answer(0x1016, right(a.sent[0][2:]))  # resposta da sessão A entregue na B
        self.assertTrue(b.closing)
        await aca.on_answer(0x1016, right(a.sent[0][2:]))
        self.assertFalse(a.closing)
        self.assertNotEqual(aca.sid, acb.sid)
        aca.close(), acb.close()

    async def test_hackshield_opcode_on_gameguard_rejected(self):
        c, ac = self.session(validator=FakeValidator())
        ac.start()
        await ac.on_answer(0x1019, b'\x00' * 56)
        self.assertTrue(c.closing)
        ac.close()

    async def test_capture_sends_fixed_query_once_and_records(self):
        query = bytes.fromhex('4e95dd29ce3a55db20b6ad97a65cc01c')
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'sub', 'cap.jsonl')
            c, ac = self.session('capture', None, capture=query, capture_out=out)
            ac.start()
            await self.settle()
            self.assertEqual((cmds(c), c.sent[0][2:]), ([0x1015], query))
            await ac.on_answer(0x1016, b'\xaa' * 16)
            await ac.on_answer(0x1016, b'\xbb' * 16)        # sem pergunta pendente: só registra
            await self.settle()
            self.assertEqual(cmds(c), [0x1015])            # nunca 0x1017 nem nova pergunta
            self.assertFalse(c.closing)
            with open(out, encoding='utf-8') as f:
                rows = [json.loads(line) for line in f]
            self.assertEqual([(r['query'], r['answer']) for r in rows], [(query.hex(), 'aa' * 16)])
            ac.close()

    def test_capture_settings(self):
        with tempfile.TemporaryDirectory() as d:
            good, bad = os.path.join(d, 'q.bin'), os.path.join(d, 'r.bin')
            with open(good, 'wb') as f:
                f.write(b'q' * 16)
            with open(bad, 'wb') as f:
                f.write(b'q' * 4)
            cfg = lambda **kw: {'anticheat': {'provider': 'gameguard', 'mode': 'capture', **kw}}
            self.assertEqual(anticheat.settings(cfg(capture_query=good)), ('gameguard', 'capture'))
            for wrong in (cfg(), cfg(capture_query=bad), cfg(capture_query=os.path.join(d, 'x')),
                          {'anticheat': {'provider': 'hackshield', 'mode': 'capture', 'capture_query': good}}):
                with self.assertRaises(ValueError):
                    anticheat.settings(wrong)

    def test_profiles_match_clients(self):
        gg, = PROFILES['gameguard']
        self.assertEqual((gg.challenge, gg.challenge_len, gg.answer, gg.answer_lens), (0x1015, 16, 0x1016, (16,)))
