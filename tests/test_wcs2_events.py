"""Eventos WCS2 (0x7012/0x6108/0x6106). Uso: python -m unittest tests.test_wcs2_events -v"""
import struct
import unittest
from gunbound.game.phase import WCS1
from gunbound.game.protocol.wcs2 import events as ev
from gunbound.util import BinaryReader
from tests.test_gm import conn
from tests.test_wcs2_jackpot import FakeDb


class FakeUsers:
    def __init__(self):
        self.saved = []

    async def set_tutorial(self, user_id, lessons):
        self.saved.append(lessons)
        return True


class FakeInv:
    def __init__(self):
        self.money, self.chest, self.gifts, self.pool = 0, [], [], None

    async def update_money(self, user_id, gold):
        self.money += gold
        return True

    async def get_money(self, user_id):
        return self.money

    async def insert_chest(self, user_id, item, acquisition, expire_type, period, volume):
        self.chest.append({'No': len(self.chest) + 1, 'Item': item, 'Volume': volume, 'Wearing': 0, 'Acquisition': 'T',
                           'Expire': None, 'PlaceOrder': 0, 'Recovered': 0})
        return len(self.chest)

    async def get_chest(self, user_id):
        return self.chest

    async def cheapest_menus(self, lo, hi, limit):
        self.pool = (lo, hi, limit)
        return [lo + 5]

    async def insert_giftitem(self, sender, receiver, menu, acquisition):
        self.gifts.append((sender, menu))
        return 1

    async def insert_giftmsg(self, *args):
        return 1


TUTORIAL = {'sender': 'GB', 'avatar_pool': 3, 1: {'gold': 100, 'items': [[700003, 30]]}, 7: {'gold': 800, 'avatar': 'head'},
            9: {'gold': 1500, 'avatar': 'flag'}}


class Points:
    async def get_points(self, uid, column):
        return 0x01020304 if column == 'TotalScore' else 0


class EventsTest(unittest.IsolatedAsyncioTestCase):
    async def run_cmd(self, cls, c):
        kw = {'user_repository': Points()} if cls in (ev.Event7012Recv, ev.Event6108Recv) else {}
        await cls(c, BinaryReader(b'')).handle(**kw)

    async def test_no_config_no_reply(self):
        c = conn('a')
        c.server.config = {}
        for cls in (ev.ReadyEventRecv, ev.LoadingDoneRecv):
            await self.run_cmd(cls, c)
        self.assertEqual(c.sent, [])

    async def test_config_replies(self):
        c = conn('a')
        c.server.config = {'event_7013_value': 7, 'event_6107_id': 3}
        for cls in (ev.Event7012Recv, ev.Event6108Recv, ev.ReadyEventRecv):
            await self.run_cmd(cls, c)
        self.assertEqual(c.last(0x7013), struct.pack('<HHI', 0x7013, 0, 7))
        self.assertEqual(c.last(0x6109), struct.pack('<HHI', 0x6109, 0, 0x01020304))  # TotalScore do banco
        self.assertEqual(c.last(0x6107), struct.pack('<HHH', 0x6107, 0, 3))

    async def end(self, c, lesson, users, inv=None):
        await ev.TutorialEndRecv(c, BinaryReader(struct.pack('<I', lesson))).handle(db=FakeDb(), user_repository=users,
                                                                                     inventory_repository=inv or FakeInv())

    async def test_tutorial_end(self):
        c, users = conn('a'), FakeUsers()
        c.server.config = {}
        c.data['game'] = {'EventScore3': 0}
        await self.end(c, 3, users)
        self.assertEqual(c.last(0x7015), struct.pack('<HH', 0x7015, 0))
        self.assertEqual(users.saved, [3])
        await self.end(c, 2, users)  # repetir lição: não regride
        await self.end(c, 99, users)  # fora de 1..9
        self.assertEqual(users.saved, [3])
        await self.run_cmd(ev.Event7012Recv, c)  # progresso sem config, mesma sessão
        self.assertEqual(c.last(0x7013), struct.pack('<HHI', 0x7013, 0, 3))

    async def test_tutorial_rewards(self):
        c, users, inv = conn('a'), FakeUsers(), FakeInv()
        c.server.config = {'tutorial': TUTORIAL}
        c.data['game'] = {'EventScore3': 0}
        c.data['profile']['Gender'] = 1
        await self.end(c, 1, users, inv)
        self.assertEqual((inv.money, [(i['Item'], i['Volume']) for i in inv.chest]), (100, [(700003, 30)]))
        self.assertEqual(c.last(0x6105)[4:], struct.pack('<I', 100))
        await self.end(c, 1, users, inv)  # repetir: nada de novo
        self.assertEqual((inv.money, len(inv.chest)), (100, 1))
        c.data['game']['EventScore3'] = 6
        await self.end(c, 7, users, inv)  # cabeça feminina 0x10000..0x18000, presente do 'sender'
        self.assertEqual((inv.money, inv.pool, inv.gifts), (900, (0x10000, 0x18000, 3), [('GB', 0x10005)]))
        await self.end(c, 9, users, inv)  # bandeira: faixa única
        self.assertEqual(inv.pool[:2], (0x38000, 0x40000))

    def test_avatar_range(self):
        self.assertEqual([ev.avatar_range(s, g) for s, g in (('body', 0), ('body', 1), ('head', 0), ('head', 1))],
                         [(0x8000, 0x10000), (0, 0x8000), (0x18000, 0x20000), (0x10000, 0x18000)])

    async def test_tutorial_progress_new_user(self):
        c = conn('a')
        c.server.config = {}
        await self.run_cmd(ev.Event7012Recv, c)
        self.assertEqual(c.last(0x7013), struct.pack('<HHI', 0x7013, 0, 0))

    def test_no_clash_with_parent(self):
        self.assertFalse(set(ev.EVENTS) & set(WCS1.handlers()))
