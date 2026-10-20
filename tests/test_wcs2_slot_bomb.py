"""WCS2 caça-níquel 0x7110 e jackpot bomb 0x6058. Uso: python -m unittest tests.test_wcs2_slot_bomb -v"""
import struct
import unittest
from unittest import mock
from gunbound.game.protocol.wcs2 import jackpot, slot_machine
from gunbound.util import BinaryReader
from tests.test_gm import conn
from tests.test_wcs2_jackpot import FakeDb, FakeInv


class Users:
    def __init__(self, tokens):
        self.tokens = tokens

    async def add_slot_tokens(self, uid, d):
        if self.tokens + d < 0:
            return False
        self.tokens += d
        return True


class Inv(FakeInv):
    def __init__(self, row=None):
        super().__init__([])
        self.row, self.cash, self.consumed = row, 600, []

    async def get_chest_item(self, uid, no):
        return self.row if self.row and no == self.row['No'] else None

    async def chest_consume(self, uid, no, v):
        self.consumed.append((no, v))
        return True

    async def update_cash(self, uid, d):
        if self.cash + d < 0:
            return False
        self.cash += d
        return True

    async def get_cash(self, uid):
        return self.cash


def player(tokens=0):
    c = conn('u')
    c.server = type('S', (), {'id': 1, 'config': {}})()
    c.data['game']['EventScore2'] = tokens
    return c


class SlotTest(unittest.IsolatedAsyncioTestCase):
    async def spin(self, c, users, inv, currency, bet, outcome):
        with mock.patch.object(slot_machine, 'spin', return_value=outcome):
            await slot_machine.SlotMachineRecv(c, BinaryReader(bytes([currency, bet]))).handle(inventory_repository=inv, user_repository=users)

    async def test_tokens_win_tokens(self):
        c, users, inv = player(50), Users(50), Inv()
        await self.spin(c, users, inv, 0, 1, (slot_machine.WIN_TOKENS, 20))  # aposta 50, prêmio 20 x 2
        self.assertEqual(c.last(0x7111)[2:], struct.pack('<HBI', 0, 0, 40))
        self.assertEqual(users.tokens, 40)
        self.assertEqual(c.last(0x7113)[2:], struct.pack('<HI', 0, 40))

    async def test_cash_win_gold(self):
        c, users, inv = player(), Users(0), Inv()
        await self.spin(c, users, inv, 1, 0, (slot_machine.WIN_GOLD, 500))
        self.assertEqual((inv.cash, inv.money), (100, 600))
        self.assertIn(0x6101, c.cmds())

    async def test_no_balance(self):
        c, users, inv = player(), Users(5), Inv()
        await self.spin(c, users, inv, 0, 0, (slot_machine.LOSE, 0))
        self.assertEqual(c.last(0x7111)[2:], b'\x01\x00')


class BombTest(unittest.IsolatedAsyncioTestCase):
    async def bomb(self, inv, card=1, no=7):
        c = player()
        await jackpot.JackpotBombRecv(c, BinaryReader(struct.pack('<BII', card, no, jackpot.CARD_ITEM + card))).handle(db=FakeDb(), inventory_repository=inv)
        return c.last(0x6059)

    async def test_rare_becomes_epic(self):
        inv = Inv({'No': 7, 'Item': jackpot.CARD_ITEM + 1, 'Volume': 13})
        reply = await self.bomb(inv)
        self.assertEqual(reply[2:9], struct.pack('<HIB', 0, jackpot.CARD_ITEM + 1, 1))
        self.assertEqual(struct.unpack_from('<III', reply, 9), (jackpot.KIND_ITEM, 99, jackpot.CARD_ITEM + 2))
        self.assertEqual((inv.consumed, inv.inserted), ([(7, 12)], [(jackpot.CARD_ITEM + 2, 1)]))

    async def test_not_enough(self):
        inv = Inv({'No': 7, 'Item': jackpot.CARD_ITEM + 2, 'Volume': 14})
        self.assertEqual((await self.bomb(inv, card=2))[2:], b'\x01\x00')


if __name__ == '__main__':
    unittest.main()
