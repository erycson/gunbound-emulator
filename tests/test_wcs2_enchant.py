"""Encantamento 0x7115 e recusas do WCS2 (slot machine, jackpot bomb). Uso: python -m unittest tests.test_phase tests.test_wcs2_enchant (a phase antes, por causa da ordem de import)"""
import struct
import unittest
from unittest import mock
from gunbound.game.protocol.wcs2 import enchant
from gunbound.util import BinaryReader
from tests.test_gm import conn
from tests.test_wcs2_jackpot import FakeDb

CASES = [(enchant.EnchantConfirmRecv, 0x7135), (enchant.JewelEnchantRecv, 0x6118)]  # 0x7410, 0x6058, 0x7110: testes próprios
RATE = {'Level': 3, 'Success': 50, 'Down1': 10, 'Down2': 10, 'Down3': 10, 'Destroy': 10, 'JewelBonus': 10}
CARD, J0, J1, NV = 204900, enchant.SPIRIT, enchant.NIHILITY, enchant.NIRVANA


class RefuseTest(unittest.IsolatedAsyncioTestCase):
    async def test_all_refuse(self):
        for cls, reply in CASES:
            c = conn('u')
            await cls(c, BinaryReader(b'\x00' * 8)).handle()
            self.assertEqual(c.last(reply)[2:], b'\x01\x00', cls.__name__)  # RTC 1, sem corpo


class OutcomeTest(unittest.TestCase):
    def go(self, items, rs):
        return [enchant.outcome(RATE, set(items), r) for r in rs]

    def test_bands(self):  # sucesso 50, queda 10/10/10, destruição 10, falha 10
        self.assertEqual(self.go([], (0, 49.9, 50, 60, 70, 80, 90, 99.9)), [0, 0, 2, 3, 4, 5, 1, 1])

    def test_spirit_takes_from_fail(self):  # sucesso 60, o resto anda 10
        self.assertEqual(self.go([J0], (59.9, 60, 99.9)), [0, 2, 5])  # a falha (10) sumiu

    def test_nihility_halves_drops(self):  # quedas 5/5/5 em [50, 65), destruição [65, 75)
        self.assertEqual(self.go([J1], (54.9, 55, 64.9, 65, 74.9, 75)), [2, 3, 4, 5, 5, 1])

    def test_nirvana_halves_destroy(self):
        self.assertEqual(self.go([enchant.NIRVANA], (84.9, 85)), [5, 1])

    def test_fortune_and_shield(self):
        self.assertEqual(self.go([J0, enchant.FORTUNE], (0, 99.9)), [0, 0])
        self.assertEqual(self.go([enchant.SHIELD], (85, 55)), [1, 2])  # nunca destrói, a queda continua


class FakeInv:
    def __init__(self, chest, rate=RATE):
        self.chest, self.rate = chest, rate
        self.consumed, self.levels, self.deleted = [], {}, []

    async def get_chest(self, user_id):
        return self.chest

    async def get_enchant_rate(self, level):
        return self.rate if self.rate and level == self.rate['Level'] else None

    async def chest_consume(self, user_id, chest_id, volume):
        self.consumed.append(chest_id)
        return True

    async def set_enchant_level(self, chest_id, level):
        self.levels[chest_id] = level

    async def delete_chest(self, user_id, chest_id):
        self.deleted.append(chest_id)
        return True


def chest(level=2, jewel_volume=1):
    return [{'No': 10, 'Item': CARD, 'Volume': 1, 'EnchantLevel': level},
            {'No': 20, 'Item': NV, 'Volume': jewel_volume, 'EnchantLevel': 0},
            {'No': 21, 'Item': J1, 'Volume': 3, 'EnchantLevel': 0}]


def body(item=CARD, pairs=((20, NV),)):  # Nirvana: sucesso 50, quedas 50-80, destrói 80-85, falha 85-100
    return BinaryReader(struct.pack('<HII', len(pairs) + 1, 10, item) + b''.join(struct.pack('<II', *p) for p in pairs))


class EnchantTest(unittest.IsolatedAsyncioTestCase):
    async def run_it(self, r, inv, rd=None):
        c, db = conn('u'), FakeDb()
        with mock.patch.object(enchant.random, 'random', return_value=r / 100):
            await enchant.EnchantRecv(c, rd or body()).handle(db=db, inventory_repository=inv)
        return c.last(0x7116), db

    async def test_c35_reply_echoes_no_and_item(self):
        c, inv = conn('u'), FakeInv(chest())
        with mock.patch.object(enchant.random, 'random', return_value=0.1):
            await enchant.EnchantC35Recv(c, body()).handle(db=FakeDb(), inventory_repository=inv)
        self.assertEqual(c.last(0x7411), struct.pack('<HHBIIH', 0x7411, 0, 0, 10, CARD, 3))

    async def test_success_raises_level_and_eats_jewels(self):
        inv = FakeInv(chest())
        reply, db = await self.run_it(10, inv, body(pairs=((20, NV), (21, J1))))
        self.assertEqual(reply, struct.pack('<HHBH', 0x7116, 0, 0, 3))
        self.assertEqual((inv.levels, inv.consumed, db.tx.done), ({10: 3}, [20, 21], 'commit'))

    async def test_fail_keeps_level(self):
        inv = FakeInv(chest())
        reply, _ = await self.run_it(95, inv)
        self.assertEqual(reply[4:], struct.pack('<BH', 1, 2))
        self.assertEqual((inv.levels, inv.consumed), ({}, [20]))

    async def test_drop_two_levels(self):
        inv = FakeInv(chest())
        reply, _ = await self.run_it(75, inv)  # Down3 (código 4) -> cai 3, para em 0
        self.assertEqual(reply[4:], struct.pack('<BH', 4, 0))
        self.assertEqual(inv.levels, {10: 0})

    async def test_destroy_deletes_item(self):
        inv = FakeInv(chest())
        reply, _ = await self.run_it(82, inv)
        self.assertEqual(reply[4:], struct.pack('<BH', 5, 0))
        self.assertEqual(inv.deleted, [10])

    async def test_refusals(self):
        for inv, rd in [
            (FakeInv(chest(jewel_volume=0)), None),  # joia acabou
            (FakeInv(chest()), body(pairs=((21, J0),))),  # par com item errado
            (FakeInv(chest()), body(pairs=((20, NV), (20, NV)))),  # mesma joia duas vezes
            (FakeInv(chest()), body(item=CARD + 1)),  # item não é o do baú
            (FakeInv(chest()[1:]), None),  # item de outro jogador
            (FakeInv(chest(level=30), rate=None), None),  # nível máximo
            (FakeInv(chest()), body(pairs=())),  # sem joia
        ]:
            reply, _ = await self.run_it(10, inv, rd)
            self.assertEqual(reply[2:], b'\x01\x00')
            self.assertEqual((inv.consumed, inv.levels, inv.deleted), ([], {}, []))
