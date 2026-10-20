"""0x6008 -> 0x6009: o original responde a todo 0x6008 (recusa = RTC 0 com n=0; falha = RTC 4). python -m unittest tests.test_gift_confirm"""
import struct
import unittest
from gunbound.game.protocol.item_gift_confirm import ItemGiftConfirmRecv
from gunbound.util import BinaryReader
from tests.test_gm import conn

GIFT = {'No': 5, 'MenuId': 0x1234, 'ExpireType': 'I'}
MENU = {'Item1': 0x30001, 'Period1': None, 'Volume1': 1, 'PriceByGoldForI': 100,
        **{f'Item{i}': None for i in range(2, 6)}}


class Crypto:
    def decrypt(self, data):
        return data


class Inventory:
    def __init__(self, found=True):
        self.found, self.calls = found, []

    async def get_giftmsg_from_giftitem(self, user_id, giftitem_id):
        return GIFT if self.found else None

    async def get_giftitem(self, user_id, giftitem_id):
        return {'Acquisition': 'G', 'Sender': 'amigo'}

    async def get_menu(self, *a):
        return MENU

    def __getattr__(self, name):  # updates/inserts: só registra
        async def call(*a):
            self.calls.append((name, *a))
            return 77
        return call


def body(giftitem_no, accept):
    return struct.pack('<IIB', (0x6008 + 0x8631607E) & 0xFFFFFFFF, giftitem_no, accept).ljust(16, b'\x00')


class GiftConfirmTest(unittest.IsolatedAsyncioTestCase):
    async def run_confirm(self, inv, accept):
        c = conn('u')
        recv = ItemGiftConfirmRecv(c, BinaryReader(body(9, accept)), db=None, config={'product_version': 1},
                                   crypto_manager=Crypto(), inventory_repository=inv)
        await recv.process()
        return c.last(0x6009)[2:]

    async def test_refuse_answers_rtc0_empty(self):
        inv = Inventory()
        self.assertEqual(await self.run_confirm(inv, 0), struct.pack('<HH', 0, 0))
        # o original devolve o ouro ao REMETENTE e a msg vira aviso 'D' para ele (Receiver=remetente, Sender=quem recusou)
        self.assertIn(('update_money', 'amigo', 100), inv.calls)
        self.assertIn(('update_giftmsg_status', 5, 'u', 'amigo', 'D'), inv.calls)

    async def test_missing_gift_answers_error(self):
        self.assertEqual(await self.run_confirm(Inventory(found=False), 1), struct.pack('<H', 4))

    async def test_accept_lists_item(self):
        out = await self.run_confirm(Inventory(), 1)
        # RTC 0, n=1, No 77, item, vestido 0, 'T' (presente), sem validade (I), u8 1 + u32 Volume, u8 0 (PlaceOrder)
        self.assertEqual(out, struct.pack('<HHIIBcBBIB', 0, 1, 77, 0x30001, 0, b'T', 0, 1, 1, 0))
