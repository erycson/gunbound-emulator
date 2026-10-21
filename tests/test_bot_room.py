"""Bot na sala: /bot add e remove, mestre e prêmio. python -m unittest tests.test_bot_room"""
import random
import unittest
from gunbound.base.enums import RoomOptions, RoomMode
import asyncio
import struct
from pathlib import Path
from unittest import mock
from gunbound.bot import match, room as bots, skill
from gunbound.game.room import GameState
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

    async def start_match(self):
        await self.cmd('/bot add')
        [b] = self.bots()
        self.master.server.index = 0
        self.room.game = GameState(1, [0, 1], {}, {0: (100, 0), 1: (b.slot * 100, 0)})
        return b, self.room.player(self.master)

    def turn_frames(self):
        """(tipo, corpo) do que o bot mandou ao mestre pelo 0x4501, só C302 e C309."""
        from tools.tunnel_decode import decode, key
        plains = [decode(raw[3:], key(0, self.room.id))[2] for raw in self.master.sent if raw[:2] == b'\x01\x45']
        return [(struct.unpack_from('<H', p)[0], p[2:]) for p in plains if p[:2] in (b'\x02\xc3', b'\x09\xc3')]

    @staticmethod
    async def settle():
        for _ in range(5):
            await asyncio.sleep(0)

    async def test_turn_replay_like_capture(self):
        """Frames do mestre da captura 1x1; as ações do slot 1 (tiro, passe, morte) entram como do próprio bot.
        O bot tem que reportar o mesmo (fase, contador) do C302 e o mesmo C309 que o humano."""
        b, me = await self.start_match()
        self.assertEqual(b.slot, 1)
        rows = [line.split() for line in Path(__file__).with_name('fixtures').joinpath('bot_turn_replay.txt')
                .read_text().splitlines() if line and not line.startswith('#')]
        expected = []
        own = (0xC400, 0xC409, match.PASS, match.DEATH)

        async def nop(*_):
            pass
        with mock.patch.multiple(match, SHOT_WAIT=0, TURN_WAIT=0, pass_turn=nop):
            for frm, kind, body in ((int(r[0]), int(r[1], 16), bytes.fromhex(r[2] if len(r) > 2 else '')) for r in rows):
                if frm == 0:
                    await match.react(self.room, b, me, kind, body)
                elif kind in own:
                    await match.react(self.room, b, b, kind, body)
                if frm == 1 and kind == match.REPORT:
                    expected.append((kind, body[:5]))
                elif frm == 1 and kind == match.DEATH_ACK:
                    expected.append((kind, body[:6]))
                await self.settle()
        got = [(k, body[:5] if k == match.REPORT else body[:6]) for k, body in self.turn_frames()]
        self.assertGreater(len(expected), 90)
        reports = [[f for f in frames if f[0] == match.REPORT] for frames in (got, expected)]
        acks = [[f for f in frames if f[0] == match.DEATH_ACK] for frames in (got, expected)]
        # o humano segura o 02 até os tanques assentarem (morte do mestre no fim do turno); o bot manda no C300.
        # Na última morte a partida acabou antes, então o bot tem um 02 a mais.
        self.assertEqual(reports[0][:-1], reports[1])
        self.assertEqual(reports[0][-1][1][0], 0x02)
        self.assertEqual(acks[0], acks[1])

    async def test_pass_on_own_turn(self):
        b, me = await self.start_match()
        frame = bots.p2p_frame(bots.p2p_key(self.room, self.master.server), 0, match.START, bytes(14))
        with mock.patch.object(match, 'TURN_WAIT', 0):
            from gunbound.game.protocol.game_play import GameTunnelRecv
            from gunbound.util.binary_buffer import BinaryReader
            await GameTunnelRecv(self.master, BinaryReader(bytes([1, 0, b.slot]) + frame)).process()  # 0x4500 ao bot
            tail = bytes.fromhex('0954001a8902ffffffff00')
            await match.react(self.room, b, me, match.NEXT, bytes([b.slot]) + struct.pack('<H', 4) + tail)
            await match.react(self.room, b, me, match.SYNC, b'\x02' + bytes(13))
            await self.settle()
        phases = [(body[0], body[1]) for k, body in self.turn_frames()]
        self.assertEqual(phases, [(0x0f, 0), (0x02, 5), (0x0f, 5)])  # início, pronto, passe
        from tools.tunnel_decode import decode, key
        plains = [decode(raw[3:], key(0, self.room.id))[2] for raw in self.master.sent if raw[:2] == b'\x01\x45']
        [c301] = [p for p in plains if p[:2] == b'\x01\xc3']
        self.assertEqual(c301[2:5 + len(tail)], b'\x01' + struct.pack('<H', match.PASS_DELAY) + tail)
        self.room.game = None  # fim da partida: nada mais sai
        n = len(self.master.sent)
        await match.react(self.room, b, me, match.PASS, bytes(14))
        self.assertEqual(len(self.master.sent), n)

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
