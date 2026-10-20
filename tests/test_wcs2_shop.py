"""WCS2 loja: presentes 0x6005, desconto 0x7118, Rena 0x7124, 0x7136. Uso: python -m unittest tests.test_wcs2_shop -v"""
import datetime
import struct
import unittest
from gunbound.game.protocol.wcs2 import shop
from gunbound.util import BinaryReader
from tests.test_gm import conn
from tests.test_rooms_shop import FakeConn, FakeInventory
from tests.test_wcs2_jackpot import FakeInv


class Users:
    def __init__(self, points=0, gifts=()):
        self.points, self.gifts = {'DiscountPoints': points, 'RenaPoints': points}, list(gifts)

    async def add_points(self, uid, column, d):
        if self.points[column] + d < 0:
            return False
        self.points[column] += d
        return True

    async def get_points(self, uid, column):
        return self.points[column]

    async def get_gift_msgs(self, uid):
        return self.gifts


def gift(no, msg):
    return {'MenuId': 0x1234, 'No': no, 'Sender': 'amigo', 'SentTime': datetime.datetime(2026, 1, 1), 'Msg': msg}


def player():
    c = conn('u')
    c.server = type('S', (), {'id': 1, 'config': {'rena': [[700096, 2, 1]]}})()
    return c


class ShopTest(unittest.IsolatedAsyncioTestCase):
    async def test_one_6005_per_gift_and_text_capped(self):
        c = player()
        await shop.GiftMsgRecv(c, BinaryReader(b'')).handle(user_repository=Users(gifts=[gift(1, 'oi'), gift(2, 'x' * 300)]))
        pkts = [p for p in c.sent if p[:2] == b'\x05\x60']
        self.assertEqual(len(pkts), 2)
        self.assertEqual(struct.unpack_from('<II', pkts[0], 2), (0x1234, 1))
        self.assertEqual((pkts[1][0x1B], len(pkts[1])), (0x82, 2 + 0x1A + 0x82))

    async def test_discount(self):
        c, users = player(), Users(points=120)
        await shop.DiscountRecv(c, BinaryReader(b'\x03')).handle(user_repository=users)
        self.assertEqual(c.last(shop.SRV_DISCOUNT)[2:], struct.pack('<HI', 0, 20))
        self.assertEqual(c.data['shop_discount'], (1, 2))
        await shop.DiscountRecv(c, BinaryReader(b'\x03')).handle(user_repository=users)  # sem pontos: recusa e volta ao preço cheio
        self.assertEqual(c.last(shop.SRV_DISCOUNT)[2:], b'\x01\x00')
        self.assertEqual((c.data['shop_discount'], users.points['DiscountPoints']), ((1, 1), 20))

    async def test_buy_uses_discount(self):
        from gunbound.game.protocol.item_buy import ItemBuyRecv
        plain = struct.pack('<IIBB', (0x6020 + 0x8631607E) & 0xFFFFFFFF, 1, 0, ord('I')) + b'\x00' * 6  # gold, permanente

        class Opened(Exception):
            pass

        class Db:
            async def transaction(self):
                raise Opened  # passou da checagem de saldo: 500 com 50% = 250 <= 300

        buyer = FakeConn('b')
        buyer.decrypt = lambda data: data
        buyer.data['shop_discount'] = (1, 2)
        with self.assertRaises(Opened):
            await ItemBuyRecv(buyer, BinaryReader(plain), db=Db(), config={}, inventory_repository=FakeInventory(300)).process()

    async def test_rena(self):
        c, users, inv = player(), Users(points=150), FakeInv([])
        await shop.RenaRecv(c, BinaryReader(b'\x64\x00\x00\x00')).handle(user_repository=users, inventory_repository=inv)
        self.assertEqual(c.last(shop.SRV_RENA)[2:], struct.pack('<HII', 0, 700096, 50))
        self.assertEqual(inv.inserted, [(700096, 2)])
        await shop.RenaRecv(c, BinaryReader(b'\x64\x00\x00\x00')).handle(user_repository=users, inventory_repository=inv)
        self.assertEqual(c.last(shop.SRV_RENA)[2:], b'\x01\x00')

    async def test_shop_enter(self):
        c = player()
        await shop.ShopEnterRecv(c, BinaryReader(b'')).handle()
        self.assertEqual(c.last(shop.SRV_SHOP_ENTER), b'\x37\x71\x00\x00')


if __name__ == '__main__':
    unittest.main()
