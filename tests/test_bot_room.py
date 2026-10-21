"""Bot na sala: /bot add e remove, mestre e prêmio. python -m unittest tests.test_bot_room"""
import random
import unittest
from gunbound.base.enums import RoomOptions, RoomMode
from gunbound.bot import room as bots, skill
from gunbound.game.protocol.enums import ServerPacket
from tests.test_rooms_shop import FakeConn, FakeServer, manager, settle

CONFIG = {**FakeServer.config, 'phase': 'WCS1', 'bots': {'enabled': True, 'gm_mobile': True, 'reward': 0.5}}


class Inventory:
    async def avatar_prices(self, lo, hi):
        return [(lo + 1, 100, 0), (lo + 2, 0, 50), (lo + 3, 5000, 0)]


def player(nick, authority=0):
    c = FakeConn(nick, authority)
    c.server = type('S', (FakeServer,), {'config': CONFIG})()
    return c


class BotRoomTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rooms = manager()
        self.master = player('mestre')
        self.room = await self.rooms.create(self.master, RoomOptions('t', RoomMode.TAG, 4, None))

    async def cmd(self, text, conn=None):
        return await bots.command(conn or self.master, text, Inventory())

    def bots(self):
        return [p for p in self.room.sorted_players() if bots.is_bot(p.conn)]

    async def test_add_balances_and_announces(self):
        msg = await self.cmd('/bot add')
        [b] = self.bots()
        self.assertIn('entrou', msg)
        self.assertEqual((b.team, b.ready), (1, True))
        self.assertAlmostEqual(b.conn.n, skill.normalize('WCS1', 1))  # iguala o mestre (TotalGrade 1)
        await settle()
        self.assertTrue(self.master.last(ServerPacket.SRV_ROOM_PLAYER_JOIN))
        self.assertIn(b.tank1, range(0x11))
        self.assertIsNone(self.room.start_check(self.master))

    async def test_grade_and_mobile_rules(self):
        self.assertIn('Patente de', await self.cmd('/bot add 50'))
        self.assertIn('só para GM', await self.cmd('/bot add 5 boomer'))
        gm = player('gm', authority=100)
        room = await self.rooms.create(gm, RoomOptions('g', RoomMode.SOLO, 4, None))
        await bots.command(gm, '/bot add 5 Boomer', Inventory())
        [b] = [p for p in room.sorted_players() if bots.is_bot(p.conn)]
        self.assertEqual((b.tank1, b.conn.data['game']['TotalGrade']), (0x05, 5))
        self.assertIn('não existe', await bots.command(gm, '/bot add 5 Phoenix', Inventory()))  # só no S2

    async def test_auto_and_suffix(self):
        self.assertIn('entrou', await self.cmd('/bot add auto auto'))  # antes: "Mobile 'auto' não existe"
        [b] = self.bots()
        nick = b.conn.data['profile']['Nickname']
        self.assertTrue(nick.endswith(bots.SUFFIX) and len(nick) <= 12)
        self.assertIn('1 bot', await self.cmd(f'/bot remove {nick[:-len(bots.SUFFIX)]}'))

    async def test_load_frames_decode_like_a_client(self):
        from tools.tunnel_decode import decode, key
        await self.cmd('/bot add')
        [b] = self.bots()
        self.master.server.index = 0
        await bots.load(self.room, delay=0)
        frames = [raw[3:] for raw in self.master.sent if raw[:2] == bytes([0x01, 0x45])]  # 0x4501: cmd, slot, frame
        got = [decode(f, key(0, self.room.id)) for f in frames]
        self.assertEqual([(seq, plain[:4]) for _, seq, plain in got],
                         [(0, bytes([1, 0x82, b.slot, 1])), (1, bytes([1, 0x82, b.slot, 2])),
                          (2, bytes([1, 0x82, b.slot, 3])), (3, bytes([0xFF, 0x82, 0, 0]))])
        self.assertTrue(all(f[3] == sum(f[4:]) & 0xFF and f[:2] == b'\x14\x80' for f in frames))

    async def test_only_master(self):
        other = player('outro')
        await self.room.join(other)
        self.assertIn('Só o mestre', await self.cmd('/bot add', other))

    async def test_remove_and_room_closes_without_humans(self):
        await self.cmd('/bot add')
        await self.cmd('/bot add')
        self.assertIn('1 bot', await self.cmd('/bot remove'))
        self.assertEqual(len(self.bots()), 1)
        await self.rooms.leave(self.master)
        self.assertIsNone(self.rooms.get(self.room.id))

    async def test_owner_never_bot(self):
        await self.cmd('/bot add')
        human = player('humano')
        await self.room.join(human)
        await self.rooms.leave(self.master)
        self.assertIs(self.room.owner, human)

    async def test_reward(self):
        await self.cmd('/bot add')
        me, [b] = self.room.player(self.master), self.bots()
        self.assertIsNone(bots.reward(self.room, b, 100, 10, CONFIG))
        self.assertEqual(bots.reward(self.room, me, 100, 10, CONFIG), (50, 5))

    def test_avatar_by_level(self):
        pools = [[(1, 10), (2, 20), (3, 30)]] * 3
        rng = random.Random(1)
        self.assertEqual(set(bots.pick_avatar(pools, 1.0, rng)) - {3, 2}, set())
        self.assertTrue(all(len(bots.pick_avatar(pools, 0.0, random.Random(i))) <= 3 for i in range(10)))


if __name__ == '__main__':
    unittest.main()
