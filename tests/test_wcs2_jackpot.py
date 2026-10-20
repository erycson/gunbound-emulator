"""Jackpot WCS2 (0x6056 -> 0x6057 + 0x6105). Uso: python -m unittest tests.test_wcs2_jackpot -v"""
import struct
import unittest
from gunbound.game.protocol.wcs2 import jackpot
from gunbound.util import BinaryReader
from tests.test_gm import conn


class FakeTx:
    def __init__(self):
        self.done = None

    async def commit(self):
        self.done = 'commit'

    async def rollback(self):
        self.done = 'rollback'


class FakeDb:
    def __init__(self):
        self.tx = FakeTx()

    async def transaction(self):
        return self.tx


class FakeInv:
    def __init__(self, chest):
        self.chest, self.inserted, self.money = chest, [], 100

    async def get_chest(self, user_id):
        return self.chest

    async def chest_consume(self, user_id, chest_id, volume):
        return True

    async def update_money(self, user_id, money):
        self.money += money
        return True

    async def get_money(self, user_id):
        return self.money

    async def insert_chest(self, user_id, item, acquisition, expire_type, period, volume):
        self.inserted.append((item, volume))
        return 99


def body(card, item):
    return BinaryReader(struct.pack('<BII', card, 7, item))


GOLD_REC = struct.pack('<III', 1, 0, 0) + bytes([0, 0, 0, 1]) + struct.pack('<I', 500) + b'\x00'


class JackpotTest(unittest.IsolatedAsyncioTestCase):
    async def run_card(self, card, item, chest, rule=None):
        c = conn('u')
        c.server = type('S', (), {'id': 1, 'config': {'jackpot': {card: rule} if rule else {}}})()
        inv, db = FakeInv(chest), FakeDb()
        await jackpot.JackpotRecv(c, body(card, item)).handle(db=db, inventory_repository=inv)
        return c, inv, db

    async def test_gold_and_item(self):
        card_item = jackpot.CARD_ITEM + 1
        rule = {'gold': [500, 500], 'items': 1, 'fail': 0, 'pool': [[98416, 2]]}
        c, inv, db = await self.run_card(1, card_item, [{'No': 5, 'Item': card_item, 'Volume': 3}], rule)
        item_rec = struct.pack('<III', 2, 99, 98416) + bytes([0, 0, 0, 1]) + struct.pack('<I', 2) + b'\x00'
        self.assertEqual(c.last(0x6057), struct.pack('<HHIBBHH', 0x6057, 0, card_item, 2, 0, 2, 0) + GOLD_REC + item_rec)
        self.assertEqual(c.last(0x6105), struct.pack('<HHI', 0x6105, 0, 600))  # gold novo na tela
        self.assertEqual(inv.inserted, [(98416, 2)])
        self.assertEqual(db.tx.done, 'commit')

    async def test_failed_item(self):
        card_item = jackpot.CARD_ITEM
        rule = {'gold': [500, 500], 'items': 1, 'fail': 100, 'pool': [[98416, 1]]}
        c, inv, _ = await self.run_card(0, card_item, [{'No': 5, 'Item': card_item, 'Volume': 1}], rule)
        self.assertEqual(c.last(0x6057)[-17:], b'\x00' * 17)  # tipo 0 = "Boost Failed"
        self.assertEqual(inv.inserted, [])

    async def test_refuse_without_card(self):
        c, _, _ = await self.run_card(2, jackpot.CARD_ITEM + 2, [])
        self.assertEqual(c.last(0x6057)[2:], b'\x01\x00')

    async def test_refuse_wrong_item_for_card(self):
        c, _, _ = await self.run_card(0, jackpot.CARD_ITEM + 3, [{'No': 5, 'Item': jackpot.CARD_ITEM + 3, 'Volume': 1}])
        self.assertEqual(c.last(0x6057)[2:], b'\x01\x00')
