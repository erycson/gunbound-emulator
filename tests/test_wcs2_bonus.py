"""WCS2 bônus de partida 0x4300. Uso: python -m unittest tests.test_wcs2_bonus -v"""
import random
import unittest
from gunbound.base.enums import RoomOptions, RoomMode
from gunbound.game.protocol.wcs2.bonus import PlayBonusRecv, roll_bonus, NO_BONUS
from gunbound.util import BinaryReader
from tests.test_rooms_shop import FakeConn, manager


class Repo:
    def __init__(self):
        self.money, self.score = {}, {}

    async def update_money(self, uid, v):
        self.money[uid] = self.money.get(uid, 0) + v

    async def add_score(self, uid, v):
        self.score[uid] = self.score.get(uid, 0) + v

    async def add_points(self, uid, column, v):
        self.points = getattr(self, 'points', {})
        self.points[uid, column] = self.points.get((uid, column), 0) + v
        return True


class BonusTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.a = FakeConn('bonus')
        self.room = await manager().create(self.a, RoomOptions('sala', RoomMode.SOLO, 2, ''))
        self.room.start()
        self.room.game.bonus_event = 2
        self.repo = Repo()

    async def send(self, kind):
        await PlayBonusRecv(self.a, BinaryReader(bytes([kind]))).handle(inventory_repository=self.repo, user_repository=self.repo)

    async def test_pays_once(self):
        await self.send(2)
        await self.send(2)
        self.assertEqual(self.repo.money, {'bonus': 500})
        self.assertEqual(self.a.sent, [])  # sem resposta

    async def test_wrong_type_ignored(self):
        await self.send(3)
        self.assertEqual(self.repo.money, {})

    def test_roll(self):
        self.assertEqual(roll_bonus({}), NO_BONUS)
        self.assertIn(roll_bonus({'bonus_event': 100}, random.Random(1)), range(10))


if __name__ == '__main__':
    unittest.main()
