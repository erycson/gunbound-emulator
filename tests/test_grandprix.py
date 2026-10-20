"""Grand Prix: layout do 0x1101, fila grupo x grupo e pontuação. Uso: python -m unittest tests.test_grandprix -v"""
import struct
import unittest
from gunbound.game.managers.grandprix import GrandPrixManager
from gunbound.game.protocol.enums import ServerPacket
from tests.test_gm import conn
from tests.test_rooms_shop import manager


class FakeRepo:
    def __init__(self, people):
        self.people = people          # Id -> linha de GrandPrix_Personal
        self.calls = []

    async def personal(self, uid):
        return self.people.get(uid)

    async def refresh_ranks(self):
        pass

    async def rankers(self, limit):
        return ([{'Category': 1, 'ScoreOnCalc': '500', 'Rank': '1', 'RankOld': '2', 'Win': '3', 'Lose': '1'},
                 {'Category': 2, 'ScoreOnCalc': '100', 'Rank': '2', 'RankOld': '1', 'Win': '1', 'Lose': '3'}],
                [{'Nickname': 'Bee', 'Score': 40, 'Rank': 1, 'RankOld': 1, 'Win': 4, 'Lose': 0}])

    async def add_personal(self, uid, score, win):
        self.calls.append(('p', uid, score, win))

    async def add_group(self, cat, score, win):
        self.calls.append(('g', cat, score, win))


def row(cat):
    return {'Score': 7, 'Rank': 3, 'RankOld': 5, 'Win': 1, 'Lose': 2, 'Category': cat}


class GrandPrixTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.a, self.b, self.c = conn('a'), conn('b'), conn('c')
        for c in (self.a, self.b, self.c):
            c.data['profile']['Id'] = c.data['profile'].get('Id') or c.data['profile']['Nickname']
        self.repo = FakeRepo({'a': row(1), 'b': row(1), 'c': row(2)})
        self.rooms = manager()
        self.gp = GrandPrixManager({'grandprix': {'enabled': True}}, self.rooms, self.repo)

    async def test_list_layout(self):
        body = await self.gp.list_body('a')
        self.assertEqual(struct.unpack_from('<H', body)[0], 2)
        self.assertEqual(struct.unpack_from('<6i', body, 2), (1, -1, 1, 500, 3, 1))  # WCS1 (padrão): Rank, Rank-RankOld, Category, Pontos, Win, Lose
        off = 2 + 48
        self.assertEqual(struct.unpack_from('<H', body, off)[0], 1)
        self.assertEqual(body[off + 2 + 24:off + 2 + 36].rstrip(b'\0'), b'Bee')
        off += 2 + 36
        self.assertEqual(body[off], 1)                       # meu grupo (categoria 1)
        self.assertEqual(struct.unpack_from('<i', body, off + 1)[0], 1)
        off += 25
        self.assertEqual(body[off], 1)                       # eu
        self.assertEqual(struct.unpack_from('<6i', body, off + 1), (3, -2, 1, 7, 1, 2))  # +8 = Category (o v495 mostra o nome do grupo)
        self.assertEqual(len(body), off + 25)

    async def test_same_group_does_not_match(self):
        await self.gp.begin(self.a)
        await self.gp.begin(self.b)
        self.assertIsNone(self.a.room)
        await self.gp.begin(self.c)
        room = self.a.room
        self.assertIsNotNone(room)
        self.assertIs(self.c.room, room)
        self.assertIsNone(self.b.room)                       # continua na fila
        self.assertEqual(room.player(self.c).team, 0)        # quem fecha a partida é o mestre (time A)
        self.assertEqual(room.player(self.a).team, 1)
        self.assertEqual(room.grandprix, (2, 1))
        self.assertIn(self.gp.on_result, room.result_hooks)   # 0x4412 chama o GP pela sala, sem o handler saber de GP
        self.assertIn(ServerPacket.SRV_ROOM_JOIN, self.c.cmds())
        self.assertIn(ServerPacket.SRV_ROOM_JOIN, self.a.cmds())

    async def test_no_group_refused(self):
        self.repo.people.pop('a')
        self.assertIsNotNone(await self.gp.begin(self.a))

    async def test_cancel(self):
        await self.gp.begin(self.a)
        self.gp.cancel(self.a)
        await self.gp.begin(self.c)
        self.assertIsNone(self.c.room)

    async def test_scores_upset(self):
        await self.gp.ranking()
        await self.gp.begin(self.a)
        await self.gp.begin(self.c)
        await self.gp.on_result(self.a.room, 0)              # time A = grupo 2 (100 pts) venceu o 1 (500): zebra
        self.assertIn(('g', 2, 20, True), self.repo.calls)
        self.assertIn(('g', 1, -20, False), self.repo.calls)
        self.assertIn(('p', 'c', 10, True), self.repo.calls)
        self.assertIn(('p', 'a', -5, False), self.repo.calls)


if __name__ == '__main__':
    unittest.main()
