"""Bot na sala: /bot add e remove, mestre e prêmio. python -m unittest tests.test_bot_room"""
import math
import random
import unittest
from gunbound.base.enums import RoomOptions, RoomMode
import asyncio
import struct
from pathlib import Path
from unittest import mock
from gunbound.bot import aim, match, room as bots, skill
from gunbound.game.room import GameState
from gunbound.game.protocol.enums import ServerPacket
from tests.test_rooms_shop import FakeConn, FakeServer, manager, settle

CONFIG = {**FakeServer.config, 'phase': 'WCS1', 'bots': {'enabled': True, 'gm_mobile': True, 'reward': 0.5}}


class Inventory:
    async def avatar_prices(self, lo, hi):
        return [(lo + 1, 100, 0), (lo + 2, 0, 50), (lo + 3, 5000, 0)]


def player(nick, authority=0):
    c = FakeConn(nick, authority)
    c.server = type('S', (FakeServer,), {'config': CONFIG, 'index': 0})()
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
        self.master.sent.clear()  # sem o 0x8102 da entrada
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

    async def test_dies_when_master_confirms(self):
        """0xc312 do mestre -> 0xc314; 0xc315 -> 0xc304 (causa 1 | 0x10, matador = quem atirou) + 0xc309 + morte."""
        b, me = await self.start_match()
        with mock.patch.object(match, 'SHOT_WAIT', 0):
            await match.react(self.room, b, me, 0xC400, bytes(40))
            await self.settle()
        await match.react(self.room, b, b, match.CHECK, bytes([b.slot]))  # não veio do mestre: nada
        await match.react(self.room, b, me, match.CHECK, bytes([b.slot + 1]))  # qualquer slot: responde
        await match.react(self.room, b, me, match.KILL, bytes([b.slot + 1]))  # outro morreu: nada
        await match.react(self.room, b, me, match.KILL, bytes([b.slot]))
        await match.react(self.room, b, me, match.KILL, bytes([b.slot]))  # repetido: já morreu
        from tools.tunnel_decode import decode, key
        plains = [decode(raw[3:], key(0, self.room.id))[2] for raw in self.master.sent if raw[:2] == bytes([0x01, 0x45])]
        kinds = [struct.unpack_from('<H', p)[0] for p in plains]
        self.assertEqual(kinds.count(match.CHECK_ACK), 1)
        [death] = [p[2:7] for p in plains if p[:2] == struct.pack('<H', match.DEATH)]
        self.assertEqual(death, struct.pack('<IB', 1 | match.DIES_NOW, me.slot))
        self.assertIn(match.DEATH_ACK, kinds)
        self.assertFalse(b.alive)
        await settle()
        self.assertTrue(self.master.last(ServerPacket.SRV_GAME_DEAD))

    async def test_only_master(self):
        other = player('outro')
        await self.room.join(other)
        self.assertIn('Só o mestre', await self.cmd('/bot add', other))

    def flat(self, w=1000, h=600, ground=500):
        return aim.Terrain(struct.pack('<II', w, h) + bytes(w * ground) + b'\x01' * (w * (h - ground)))

    def test_terrain_and_flight(self):
        t = self.flat()
        self.assertEqual(t.ground(10), 500)
        t.carve(300, 500, 10)
        self.assertEqual(t.ground(300), 511)
        self.assertEqual(t.ground(320), 500)
        right, left = aim.fly(t, 500, 500, 45, 100, 98, (0, 0)), aim.fly(t, 500, 500, 135, 100, 98, (0, 0))
        self.assertLess(abs((right[0] - 500) - (500 - left[0])), 3)  # sem vento, espelhado
        self.assertGreater(aim.fly(t, 500, 500, 45, 100, 98, (20, 0))[0], right[0])  # vento a favor leva mais longe

    def test_shot_body_like_capture(self):
        """Tiro do mestre na captura: mesmos bytes com o mesmo cano."""
        with mock.patch.object(aim, 'muzzle', return_value=(-17, 21)):
            body = match.shot_body(1480, 1410, 145, 184, (10, 84), (1087, 1388))
        self.assertEqual(body.hex(' '), 'c8 05 82 05 01 00 91 00 b8 00 01 ef ff 15 00 ef ff 15 00 ef ff 15 00 0a 00 54 00 '
                                        '00 01 08 3f 04 6c 05')

    def test_shot_body_v584(self):
        """Tiro do admin no v584 (para a esquerda): lado 0, força x5, impactos em 30; para a direita, lado 1."""
        with mock.patch.object(aim, 'muzzle', return_value=(-31, 13)):
            body = match.shot_body(1052, 1093, 200, 238, (0, 204), (762, 1227), True)
        self.assertEqual(body.hex(' '), '1c 04 45 04 00 00 c8 00 a6 04 01 e1 ff 0d 00 e1 ff 0d 00 e1 ff 0d 00 00 00 cc 00 '
                                        '00 00 00 01 08 fa 02 cb 04')
        self.assertEqual(match.shot_body(1, 1, 65, 100, (0, 0), None, True)[4], 1)
        t = self.flat()
        conn = mock.Mock(terrain=t, v584=True)
        match.craters(conn, match.shot_body(1052, 400, 200, 238, (0, 204), (762, 500), True))
        self.assertGreater(t.ground(762), 500 + 10)

    def test_aim_avoids_self_and_walls(self):
        self.assertIsNone(aim.stage_name(1, 2))  # lado C: o mapa não está no xfs do S1
        t = self.flat()
        for y in range(300, 500):  # parede de 6 px entre os dois (o tiro anda 17 px por passo)
            t.px[y * t.w + 400:y * t.w + 406] = bytes([1]) * 6
        self.assertLess(aim.fly(t, 300, 500, 30, 200, 98, (0, 0))[0], 406)  # não atravessa
        angle, power, hit, _ = aim.best_shot(t, (300, 500), (600, 500), 98, (0, 0))
        self.assertLess(abs(hit[0] - 600), 20)
        self.assertGreaterEqual(math.dist(hit, (300, 500)), aim.SAFE)

    async def own_shot(self, roll, shot=True, version=0):
        """Turno do bot num mapa plano: (corpos dos frames que ele mandou por tipo, corpo do 0xc400)."""
        self.master.data['client_version'] = version
        b, me = await self.start_match()
        b.conn.layout = 'WCS2'
        self.room.game.spawns = {me.slot: (700, 0), b.slot: (200, 0)}
        frame = bots.p2p_frame(bots.p2p_key(self.room, self.master.server), 0, match.START, bytes(14))
        with mock.patch.object(aim.Terrain, 'load', return_value=self.flat()),                 mock.patch.object(match, 'TURN_WAIT', 0), mock.patch.object(match, 'AIM_WAIT', 0),                 mock.patch.object(match, 'SHOT_WAIT', 0), mock.patch.object(match.random, 'random', return_value=roll):
            from gunbound.game.protocol.game_play import GameTunnelRecv
            from gunbound.util.binary_buffer import BinaryReader
            await GameTunnelRecv(self.master, BinaryReader(bytes([1, 0, b.slot]) + frame)).process()
            tail = bytes.fromhex('0954001a8902ffffffff00')
            await match.react(self.room, b, me, match.NEXT, bytes([b.slot]) + struct.pack('<H', 4) + tail)
            await match.react(self.room, b, me, match.SYNC, b'\x02' + bytes(13))
            for _ in range(5):
                await self.settle()
        from tools.tunnel_decode import decode, key
        plains = [decode(raw[3:], key(0, self.room.id))[2] for raw in self.master.sent if raw[:2] == b'\x01\x45']
        sent = {}
        for p in plains:
            sent.setdefault(struct.unpack_from('<H', p)[0], []).append(p[2:])
        return sent, sent[match.SHOT][0] if shot else None

    async def test_shoots_on_own_turn(self):
        """Mira no inimigo com o vento do C300: 0x8006, 0xc400 e o 0e com delay; sem passe."""
        sent, c400 = await self.own_shot(0.0)
        self.assertNotIn(match.PASS, sent)
        self.assertEqual(sent[match.AIM][0][:6], struct.pack('<HH', 200, 500) + b'\x00\x01')
        x, y, angle, power = *struct.unpack_from('<HH', c400), *struct.unpack_from('<hH', c400, 6)
        self.assertEqual((x, y), (200, 500))
        self.assertTrue(25 <= angle <= 85 and 40 <= power <= 400)
        self.assertEqual(struct.unpack_from('<hh', c400, 23), (9, 84))
        self.assertEqual(c400[28], 1)
        hx, hy = struct.unpack_from('<HH', c400, 30)
        self.assertLess(abs(hx - 700), 20)
        self.assertIn(struct.pack('<BII', 0x0e, 5, match.SHOT_DELAY), [r[:9] for r in sent[match.REPORT]])

    async def test_shoots_v584(self):
        """Humano no v584: alvo à direita -> lado 1 no 0xc400 e no 0x8006 (trocado), força x5, impactos em 30."""
        sent, c400 = await self.own_shot(0.0, version=584)
        self.assertEqual(c400[4:6], b'\x01\x00')
        self.assertEqual(sent[match.AIM][0][4:6], b'\x00\x01')
        self.assertEqual(struct.unpack_from('<H', c400, 8)[0] % match.V584_POWER, 0)
        self.assertEqual(c400[30], 1)
        self.assertLess(abs(struct.unpack_from('<H', c400, 32)[0] - 700), 20)

    async def test_misses_by_skill(self):
        _, c400 = await self.own_shot(1.0)
        self.assertGreater(abs(struct.unpack_from('<H', c400, 30)[0] - 700) if c400[28] else 999, 40)

    async def test_passes_when_aim_fails(self):
        with mock.patch.object(match, 'aim_at', side_effect=ValueError('mapa')):
            sent, _ = await self.own_shot(0.0, shot=False)
        self.assertIn(match.PASS, sent)

    async def test_ready_over_p2p_and_after_match(self):
        """O mestre só vê o bot pronto pelo 0x8102 03 do túnel; depois da partida o bot continua pronto."""
        await self.cmd('/bot add')
        [b] = self.bots()
        from tools.tunnel_decode import decode, key
        plains = [decode(raw[3:], key(self.master.server.index, self.room.id))[2]
                  for raw in self.master.sent if raw[:2] == bytes([0x01, 0x45])]
        self.assertIn(struct.pack('<HB', bots.READY, 3), [p[:3] for p in plains])
        self.room.game = GameState(1, [0, 1], {}, {0: (100, 0), 1: (200, 0)})
        self.room.finish()
        self.assertTrue(b.ready)
        self.assertFalse(self.room.player(self.master).ready)

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
