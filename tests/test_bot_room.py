"""Bot na sala: /bot add e remove, mestre e prêmio. python -m unittest tests.test_bot_room"""
import math
import os
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

CONFIG = {**FakeServer.config, 'phase': 'WCS1', 'bots': {'enabled': True, 'gm_mobile': True, 'reward': 0.5,
                                                                   'maps': 'tests/sem-mapas'}}


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
            for _ in range(5):
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

    def test_digs_only_simulated_shots(self):
        """Tiro de bot que a mira não simula (baleia) não cava a cópia; o de humano e o tiro normal de bot cavam."""
        from types import SimpleNamespace as NS
        bot = lambda slot: NS(slot=slot, conn=NS(layout='WCS2', data={'bot': True}))
        room = NS(game=NS(tanks={1: (0x17, 0), 2: (0x00, 0)}))
        body = match.shot_body(100, 500, 60, 200, (0, 0), (300, 500), True)
        with mock.patch.object(match, 'is_bot', side_effect=lambda c: hasattr(c, 'data')):
            self.assertFalse(match.digs(room, bot(1), match.SHOT, body))
            self.assertTrue(match.digs(room, bot(2), match.SHOT, body))
            self.assertTrue(match.digs(room, NS(slot=3, conn=object()), match.SHOT, body))

    def test_aim_avoids_self_and_walls(self):
        self.assertIsNone(aim.stage_name(1, 2))  # lado C: o mapa não está no xfs do S1
        t = self.flat()
        for y in range(300, 500):  # parede de 6 px entre os dois (o tiro anda 17 px por passo)
            t.px[y * t.w + 400:y * t.w + 406] = bytes([1]) * 6
        self.assertLess(aim.fly(t, 300, 500, 30, 200, 98, (0, 0))[0], 406)  # não atravessa
        angle, power, hit, _ = aim.best_shot(t, (300, 500), (600, 500), 98, (0, 0))
        self.assertLess(abs(hit[0] - 600), 20)
        self.assertGreaterEqual(math.dist(hit, (300, 500)), aim.SAFE)
        me, enemy = (300, 500), (640, 500)
        self.assertFalse(aim.safe((520, 500), enemy, [me, (500, 500)]))  # cai no aliado
        self.assertTrue(aim.safe((630, 500), enemy, [me, (500, 500)]))
        self.assertTrue(aim.safe((630, 500), enemy, [me, (620, 500)]))  # aliado colado no inimigo: atira mesmo assim
        self.assertFalse(aim.safe(None, enemy, [me]))

    @staticmethod
    def fake_xfs(files: dict) -> bytes:
        """XFS2 mínimo que tools/xfs_sync/xfs_reader.py lê: um bloco zlib final por arquivo, cabeçalho e tabela."""
        import zlib
        body, table = bytearray(4), bytearray()
        for name, data in files.items():
            z = zlib.compress(data)
            table += name.encode().ljust(112, b'\x00') + struct.pack('<IIII', len(body), 1, len(data), len(z))
            body += struct.pack('<HBH3x', len(data), 0, len(z)) + z
        ptr = len(body)
        body += b'\x00' + zlib.compress(b'XFS2' + struct.pack('<II', 0, len(files)).ljust(60, b'\x00'))
        body += bytes(3) + zlib.compress(bytes(table))
        body[:4] = struct.pack('<I', ptr)
        return bytes(body)

    def test_import_maps(self):
        """tools/import_maps.py: stage.dat do v584 (prefixo em +128, mapa + lado * 18) vira .lnd.gz + stages-v584.txt;
        .lnd que mudou entre versões ganha nome próprio. O v584 grava lado % 2, então o lado D usa o B."""
        from tools import import_maps
        lzhuf, _ = import_maps._gbedit()
        size, rec, off, per_side, _ = import_maps.LAYOUTS['v584']
        stage = bytearray(size)
        for side, name in ((0, b'MineC'), (1, b'MineCB')):
            at = (2 + side * per_side) * rec + off
            stage[at:at + len(name)] = name
        lnd = struct.pack('<II', 4, 2) + bytes([0, 0, 0, 0, 1, 1, 1, 1])
        lnd_b = struct.pack('<II', 4, 2) + bytes([0, 0, 0, 0, 0, 0, 1, 1])
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            xfs, out = Path(d) / 'graphics.xfs', Path(d) / 'maps'
            xfs.write_bytes(self.fake_xfs({'stage.dat': b'vers' + lzhuf.encode(bytes(stage)), 'minec.lnd': lnd,
                                           'mineCB.lnd': lnd_b}))
            table, lnds = import_maps.read(xfs, 'v584')
            self.assertEqual(table, {(2, 0): 'minec', (2, 1): 'minecb'})
            out.mkdir()
            import gzip
            (out / 'minec.lnd.gz').write_bytes(gzip.compress(lnd_b))  # o do s1 era outro
            self.assertEqual(import_maps.save(out, 'v584', table, lnds), ['minec'])
            self.assertEqual((out / 'stages-v584.txt').read_text().split(), '2 0 minec.v584 2 1 minecb'.split())
            self.assertEqual(aim.load_map(2, 0, 'v584', out).ground(1), 1)
            self.assertEqual(aim.load_map(2, 3, 'v584', out).px, bytearray(lnd_b[8:]))
            self.assertIsNone(aim.load_map(3, 0, 'v584', out))  # mapa fora da tabela: o bot passa a vez

    async def test_terrain_without_imported_maps(self):
        """Sem server/maps, o graphics.xfs do S1; o v584 pede o lado % 2. Erro de leitura avisa uma vez só."""
        self.master.data['client_version'] = 584
        b, _ = await self.start_match()
        b.conn.layout = 'WCS2'
        self.room.options.settings |= 3 << 16
        flat = self.flat()
        match._warned.clear()
        with mock.patch.object(aim.Terrain, 'load', return_value=flat) as loads:
            await match.prepare(self.room, b)
        self.assertIs(b.conn.terrain, flat)
        self.assertEqual(loads.call_args.args[0].name, 'graphics.xfs')
        self.assertEqual(loads.call_args.args[1:], (self.room.game.map, 1))
        with mock.patch.object(aim.Terrain, 'load', side_effect=OSError('ilegível')),                 mock.patch('builtins.print') as said:
            await match.prepare(self.room, b)
            await match.prepare(self.room, b)
        self.assertIsNone(b.conn.terrain)
        self.assertEqual(said.call_count, 1)

    async def own_shot(self, roll, shot=True, version=0, bar=()):
        """Turno do bot num mapa plano: (corpos dos frames que ele mandou por tipo, corpo do 0xc400)."""
        self.master.data['client_version'] = version
        b, me = await self.start_match()
        b.conn.layout = 'WCS2'
        self.room.game.spawns = {me.slot: (700, 0), b.slot: (200, 0)}
        frame = bots.p2p_frame(bots.p2p_key(self.room, self.master.server), 0, match.START, bytes(14))
        with mock.patch.object(aim.Terrain, 'load', return_value=self.flat()),                 mock.patch.object(match, 'TURN_WAIT', 0), mock.patch.object(match, 'AIM_WAIT', 0),                 mock.patch.object(match, 'SHOT_WAIT', 0), mock.patch.object(match.random, 'random', return_value=roll), mock.patch.object(match, 'SHOT2', 0),                 mock.patch.object(match, 'BAR', bar), mock.patch.object(match, 'ITEM_WAIT', 0):
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
        self.assertTrue(10 <= angle <= 55 and 40 <= power <= 400)  # Armor no plano: a faixa de mira dele
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

    async def test_item_before_shot(self):
        """Acerto previsto: Dual. 0xc401 (espaço 0, ff, código 1, x, y, lado) antes do tiro; o 0xc400 leva 01 ff nos bytes
        27..28 e os 2 impactos; o item sai da barra."""
        with mock.patch.object(match, 'pick_item', return_value=match.DUAL):  # escolha: test_item_choice_and_change_wind
            sent, c400 = await self.own_shot(0.0, version=584, bar=match.BAR)
        self.assertEqual(sent[match.ITEM][0][:9], struct.pack('<BBHHHB', 0, 0xFF, 1, 200, 500, 1))
        self.assertEqual(c400[27:29], b'\x01\xff')
        self.assertEqual(c400[30], 2)
        [b] = self.bots()
        self.assertNotIn(match.DUAL, b.conn.items)

    def test_item_choice_and_change_wind(self):
        from types import SimpleNamespace as NS
        conn = NS(v584=True, items=None, last=('alvo',), steady=False, tail=bytes([20]) + struct.pack('<H', 300))
        self.assertIsNone(match.pick_item(conn, (45, 100, (1, 1), 1)))  # acerto sem ter acertado antes: sem item
        conn.steady = True
        self.assertEqual(match.pick_item(conn, (45, 100, (1, 1), 1)), match.DUAL)
        self.assertIsNone(match.pick_item(conn, (45, 100, (1, 1), 'ss')))
        conn.items.remove(match.DUAL)
        self.assertEqual(match.pick_item(conn, (45, 100, (1, 1), 2)), match.POWER_UP)
        conn.last = None
        self.assertEqual(match.pick_item(conn, (45, 100, (1, 1), 1)), match.BUNGE)  # cavando
        conn.blind = True
        self.assertIsNone(match.pick_item(conn, (45, 100, (1, 1), 1)))  # tiro não simulado: não está cavando
        conn.blind = False
        self.assertIsNone(match.pick_item(NS(v584=False, items=None, last=('alvo',)), (45, 100, None, 1)))
        match.flip_wind(conn)
        self.assertEqual(match.wind(conn), (20, 120))
        # vento forte contra: só o vento virado deixa acertar
        t = self.flat(w=1400)
        bot = NS(slot=0, team=0, alive=True, conn=NS(terrain=t, seen={}, layout='WCS2', v584=True, items=None,
                                                     tail=bytes([26]) + struct.pack('<H', 180), pos=None))
        room = NS(players={0: bot, 1: NS(slot=1, team=1, alive=True)}, game=NS(tanks={}, spawns={0: (100, 0), 1: (1300, 0)}))
        with mock.patch.object(match, 'spot_error', side_effect=lambda r, b, me: 0 if match.wind(b.conn)[1] == 0 else 99):
            self.assertTrue(match.flip_helps(room, bot))
            self.assertEqual(match.wind(bot.conn), (26, 180))  # a conta não muda o vento de verdade
            bot.conn.tail = bytes([26]) + struct.pack('<H', 0)
            self.assertFalse(match.flip_helps(room, bot))

    async def test_shot2_ss_and_repeat(self):
        """Tiro 2 só nos mobiles em que ele voa como o 1; SS (0xc409) a cada SS_EVERY tiros. O tiro que acertou se repete
        sem sortear erro: com o mesmo vento, mesmo ângulo e força 1..2% diferente; com outro vento, mira nova."""
        conn = mock.Mock(layout='WCS2', shots=0)
        rng = mock.Mock(random=mock.Mock(return_value=0.0))
        self.assertEqual([match.pick_kind(conn, 0x00, rng) for _ in range(6)], [1] * 6)  # sem acerto ainda: tiro 1
        self.assertEqual([match.pick_kind(conn, 0x00, rng, True) for _ in range(3)], ['ss', 2, 2])  # SS guardado
        self.assertEqual([match.pick_kind(conn, 0x02, rng, True) for _ in range(3)], [1, 1, 'ss'])  # Nak: o 2 cava
        conn.shots = 0
        self.assertEqual([match.pick_kind(conn, 0x05, rng, True) for _ in range(6)], [1] * 6)  # Boomer: bumerangue
        self.assertEqual(match.shot_body(1, 1, 65, 100, (0, 0), None, True, shot2=True)[4:6], bytes([1, 1]))
        b, me = await self.start_match()
        b.conn.layout, b.conn.terrain, b.conn.tail, b.conn.shots = 'WCS2', self.flat(), b'', 0
        self.room.game.spawns = {me.slot: (700, 0), b.slot: (200, 0)}
        rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda s: s[0], uniform=lambda lo, hi: hi)
        angle, power, hit, _, _ = match.aim_at(self.room, b, rng)
        self.assertLess(abs(hit[0] - 700), 20)
        rng.random.return_value = 0.99  # erraria pela chance de acerto
        again = match.aim_at(self.room, b, rng)
        self.assertEqual(again[:2], (angle, round(power * 0.98)))
        b.conn.tail = bytes([20]) + struct.pack('<H', 0)  # vento novo
        self.assertLess(abs(match.aim_at(self.room, b, rng)[2][0] - 700), 20)
        self.room.game.tanks[b.slot] = (0x05, 0x05)  # Boomer: a mira não simula o bumerangue, não conta como acerto
        match.aim_at(self.room, b, rng)
        self.assertIsNone(b.conn.last)

    def test_angles_follow_mobile_range(self):
        """Mira só na faixa do characterdata, somada à inclinação (partida de 21/10: Phoenix/Armor atiravam num ângulo
        que o cano não mostrava). O Nak (125..175) atira para a direita olhando para a esquerda."""
        from types import SimpleNamespace as NS
        t = self.flat(w=1400)
        armor = aim.angles(t, 300, 500, 0x00)
        self.assertEqual(min(a for a, f in armor if f == 1), 10)
        self.assertEqual(max(a for a, f in armor if f == 1), 55)
        self.assertEqual({a for a, f in armor if f == 0}, {180 - a for a, f in armor if f == 1})
        self.assertEqual(sorted(a for a, f in aim.angles(t, 300, 500, 0x02) if f == 0), list(range(5, 56, 5)))
        # o byte do fio 0x0D (Aduka) é a classe do CyberNaK no WC: mira para trás (bot atirava para frente); o TH não troca
        self.assertEqual((aim.model('WCS2', 0x0D), aim.model('WCS1', 0x0E), aim.model('TH', 0x0D)), (0x0F, 0x10, 0x0D))
        self.assertTrue(all(a > 90 for a, f in aim.angles(t, 300, 500, aim.model('WCS2', 0x0D)) if f == 1))
        with mock.patch.object(aim, 'slope', return_value=10):  # subida para o lado que olha: o cano levanta
            self.assertEqual(max(a for a, f in aim.angles(t, 300, 500, 0x00) if f == 1), 65)
        bot = NS(slot=0, team=0, alive=True, conn=NS(terrain=t, seen={}, tail=b'', layout='WCS2', shots=0, last=None,
                                                     n=1.0, server=NS(config=CONFIG)))
        room = NS(players={0: bot, 1: NS(slot=1, team=1, alive=True)},
                  game=NS(tanks={0: (0x02, 0x02)}, spawns={0: (300, 0), 1: (900, 0)}))
        angle, _, hit, _, face = match.aim_at(room, bot, mock.Mock(random=mock.Mock(return_value=0.0)))
        self.assertEqual((face, angle <= 55), (0, True))
        self.assertLess(abs(hit[0] - 900), 20)

    def test_picks_easiest_enemy(self):
        """O inimigo mais perto está dentro de uma caixa: o bot mira no de longe, que o tiro alcança."""
        from types import SimpleNamespace as NS
        t = self.flat(w=1400)
        for y in range(350, 500):  # caixa fechada em volta do x 600
            for x in range(520, 680):
                t.px[y * t.w + x] = int(y < 356 or x < 526 or x >= 674)
        bot = NS(slot=0, team=0, alive=True,
                 conn=NS(terrain=t, seen={}, tail=b'', layout='WCS2', shots=0, last=None, n=1.0,
                         server=NS(config=CONFIG)))
        near, far = (NS(slot=i, team=1, alive=True) for i in (1, 2))
        room = NS(players={0: bot, 1: near, 2: far},
                  game=NS(tanks={}, spawns={0: (300, 0), 1: (600, 400), 2: (1100, 0)}))
        rng = mock.Mock(random=mock.Mock(return_value=0.0))
        hit = match.aim_at(room, bot, rng)[2]
        self.assertLess(abs(hit[0] - 1100), 20)
        self.assertEqual(bot.conn.last[0], far.slot)

    def test_never_targets_teammate(self):
        """Solo também é time A x B (partida de 21/10: no Solo os bots miravam no aliado mais fácil)."""
        from types import SimpleNamespace as NS
        bot = NS(slot=0, team=1, alive=True,
                 conn=NS(terrain=self.flat(w=1400), seen={}, tail=b'', layout='WCS2', shots=0, last=None, n=1.0,
                         server=NS(config=CONFIG)))
        friend, enemy = NS(slot=1, team=1, alive=True), NS(slot=2, team=0, alive=True)
        room = NS(players={0: bot, 1: friend, 2: enemy}, game=NS(tanks={}, spawns={0: (300, 0), 1: (600, 0), 2: (1200, 0)}))
        hit = match.aim_at(room, bot, mock.Mock(random=mock.Mock(return_value=0.0)))[2]
        self.assertLess(abs(hit[0] - 1200), 20)

    def test_digs_or_passes(self):
        """Inimigo dentro de uma caixa grossa: o bot cava (o impacto fica na caixa e a cratera entra na cópia do mapa).
        Bot preso numa caixa colada nele: nenhum tiro seguro, passa a vez."""
        from types import SimpleNamespace as NS

        def box(t, x0, x1, y0, thick):
            for y in range(y0, 500):
                for x in range(x0, x1):
                    t.px[y * t.w + x] = int(y < y0 + thick or x < x0 + thick or x >= x1 - thick)

        def room_with(t, me=(300, 400)):
            bot = NS(slot=0, team=0, alive=True, conn=NS(terrain=t, seen={}, tail=b'', layout='WCS2', shots=0,
                                                         last=None, n=1.0, server=NS(config=CONFIG)))
            enemy = NS(slot=1, team=1, alive=True)
            return bot, NS(players={0: bot, 1: enemy},
                           game=NS(tanks={}, spawns={0: me, 1: (1100, 400)}))
        rng = mock.Mock(random=mock.Mock(return_value=0.0))
        t = self.flat(w=1400)
        box(t, 1000, 1200, 300, 40)
        bot, room = room_with(t)
        hit = match.aim_at(room, bot, rng)[2]
        self.assertTrue(1000 <= hit[0] < 1200 and hit[1] < 500)
        t = self.flat(w=1400)
        box(t, 250, 350, 455, 10)
        bot, room = room_with(t, (300, 470))
        self.assertIsNone(match.aim_at(room, bot, rng))

    def test_walk_like_client(self):
        """Plano: 100 quadros, 1,5 px por quadro. Parede de 40 px barra antes dela. Degrau: 0x8402 uma vez e cai."""
        t = self.flat(w=1400)
        frames = list(aim.walk(t, 600, 500, 1))
        self.assertEqual((len(frames), frames[-1]), (100, (750, 500, False)))
        wall = self.flat(w=1400)
        for y in range(460, 500):
            for x in range(700, 720):
                wall.px[y * wall.w + x] = 1
        self.assertLessEqual(list(aim.walk(wall, 600, 500, 1))[-1][0], 700 - aim.TANK_W // 2)
        step = self.flat(w=1400)
        for y in range(500, 540):
            for x in range(650, 1400):
                step.px[y * step.w + x] = 0
        frames = list(aim.walk(step, 600, 500, 1))
        self.assertEqual(sum(f[2] for f in frames), 1)
        self.assertEqual(frames[-1][1], 540)

    def test_walks_for_aim_and_away_from_edge(self):
        """Debaixo de um teto baixo não há tiro: anda para fora. Na beira de um penhasco: anda para longe dela."""
        from types import SimpleNamespace as NS

        def room_with(t, me, enemy):
            bot = NS(slot=0, team=0, alive=True, conn=NS(terrain=t, seen={}, tail=b'', layout='WCS2', shots=0,
                                                         last=None, n=1.0, server=NS(config=CONFIG), pos=None,
                                                         v584=True))
            return bot, NS(players={0: bot, 1: NS(slot=1, team=1, alive=True)},
                           game=NS(tanks={0: (0x0C, 0x0C)}, spawns={0: me, 1: enemy}))  # Grub: mira de 25 a 65
        cave = self.flat(w=1400)
        for y in range(458, 466):
            for x in range(150, 420):
                cave.px[y * cave.w + x] = 1
        bot, room = room_with(cave, (300, 500), (1100, 400))
        path = match.route(room, bot)
        self.assertGreater(match.spot_error(room, bot, (300, 500)), match.MOVE_ERR)
        self.assertLessEqual(match.spot_error(room, bot, path[-1][:2]), match.MOVE_ERR)
        edge = self.flat(w=1400)
        for y in range(500, 600):
            for x in range(620, 1000):
                edge.px[y * edge.w + x] = 0
        bot, room = room_with(edge, (610, 500), (1300, 400))
        path = match.route(room, bot)
        self.assertEqual(path[-1][3], 0)
        self.assertEqual(aim.risk(edge, *path[-1][:2]), 0)
        bot, room = room_with(self.flat(w=1400), (300, 500), (1100, 400))
        self.assertEqual(match.route(room, bot), [])  # já tem tiro: fica
        bot, room = room_with(cave, (300, 500), (1100, 400))
        bot.conn.v584 = False
        self.assertEqual(match.route(room, bot), [])  # andar só estudado no v584

    async def test_walk_frames_before_shot(self):
        """Um 0x8005 por quadro, 0x8402 no degrau, e o tiro sai de onde ele parou."""
        path = [(201, 500, False, 1), (203, 500, True, 1)]
        with mock.patch.object(match, 'route', return_value=path), mock.patch.object(match, 'STEP_TIME', 0):
            sent, c400 = await self.own_shot(0.0)
        self.assertEqual([w[:4] for w in sent[match.WALK]], [struct.pack('<HH', 201, 500), struct.pack('<HH', 203, 500)])
        self.assertEqual([m[:5] for m in sent[match.MOVE]], [struct.pack('<HHB', 203, 500, 1)])
        self.assertEqual(struct.unpack_from('<H', c400)[0], 203)

    def test_weather_from_next(self):
        """0xc300 do admin (v584, 4 jogadores): o evento da rodada vem no u8 5 do 0xc300 anterior; coluna nova entra no
        1º turno da rodada; o coringa (slot 6) traz o tipo no 1º byte."""
        from types import SimpleNamespace as NS
        conn = NS()
        frames = ['0c9b00f9f900 007b1202 ffffffffff', '0c9b00f9f908 ffffffffffff',  # c=0 força; c=3 avisa espelho
                  '0c9b00f9f908 ffffffff 00725a03 ff', '0c9b00f9f901 ffffffffffff',  # c=4 espelho; c=7 tornado
                  '0c9b00f9f901 ff 0051a403 ffffffff', '0c9b00f9f903 ffffffffffff',  # c=8 tornado; c=15 vento
                  '0c9b00f9f909 ffffffffffff', '0c9b00f9f909 ffffffffff 034b2302']  # c=16 nada; c=20 coringa
        seen = []
        for f in frames:
            match.update_weather(conn, bytes.fromhex(f.replace(' ', '')))
            seen.append(list(conn.weather))
        self.assertEqual(seen[0], [('force', 530, 123)])
        self.assertEqual(seen[2], [('mirror', 858, 114)])
        self.assertEqual(seen[4], [('tornado', 932, 81)])
        self.assertEqual(seen[6], [])
        self.assertEqual(seen[7], [('blackforce', 547, 75)])
        conn = NS()
        for f in ('0c9b00f9f900 007b1202 ffffffffff', '0c9b00f9f900 00641c02 ffffffffff'):  # força em 530 e em 540
            match.update_weather(conn, bytes.fromhex(f.replace(' ', '')))
        self.assertEqual(conn.weather, [('force', 535, 184)])  # perto de outra igual: funde, largura x1,5

    def test_weather_bends_the_shot(self):
        t = self.flat(w=1400, h=1000, ground=900)
        crossed = set()
        plain = aim.fly(t, 300, 900, 45, 200, 98, (0, 0))
        spun = aim.fly(t, 300, 900, 45, 200, 98, (0, 0), weather=[('tornado', 500, 100)], crossed=crossed)
        self.assertIn('tornado', crossed)
        self.assertGreater(spun[0], plain[0])  # sem gravidade dentro do tornado: voa mais longe
        low = aim.fly(t, 300, 900, 20, 150, 98, (0, 0))
        self.assertGreater(low[0], 480)
        back = aim.fly(t, 300, 900, 20, 150, 98, (0, 0), weather=[('mirror', 420, 60)])
        self.assertLess(back[0], 400)  # o espelho rebate o vx (Y >= 640)
        up = self.flat(w=1400)  # chão em 500: o tiro todo fica acima de Y 640 e o espelho não rebate
        self.assertEqual(aim.fly(up, 300, 500, 20, 150, 98, (0, 0), weather=[('mirror', 420, 60)]),
                         aim.fly(up, 300, 500, 20, 150, 98, (0, 0)))
        err = aim.best_shot(t, (300, 900), (900, 900), 98, (0, 0), weather=[('force', 900, 120)])[3]
        self.assertLessEqual(err, 0)  # acerto que passa pela força conta melhor

    async def test_ss_goes_as_c409(self):
        with mock.patch.object(match, 'pick_kind', return_value='ss'):
            sent, _ = await self.own_shot(0.0, shot=False)
        self.assertIn(match.SS, sent)
        self.assertNotIn(match.SHOT, sent)

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

    async def test_player_info_at_load_v584(self):
        """No começo da partida (v584) o bot manda o 0x8400 como o humano: apelido nos 2 nomes, GP com sinal em 52, zeros
        do 57 em diante (pct de dano/cratera 163/165 = 0); no S1 não manda."""
        from tools.tunnel_decode import decode, key
        for version, sends in ((584, True), (0, False)):
            self.master.data['client_version'] = version
            b, _ = await self.start_match()
            self.master.sent.clear()
            await bots.load(self.room, 0)
            plains = [decode(raw[3:], key(0, self.room.id))[2] for raw in self.master.sent if raw[:2] == b'\x01\x45']
            info = [p[2:] for p in plains if p[:2] == struct.pack('<H', bots.PLAYER_INFO)]
            self.assertEqual(bool(info), sends)
            if sends:
                nick = b.conn.data['profile']['Nickname'].encode('latin-1')
                self.assertEqual(info[0][:len(nick)], nick)
                self.assertEqual(info[0][16:16 + min(12, len(nick))], nick[:12])
                self.assertEqual(info[0][52], 1)
                self.assertEqual(info[0][57:bots.INFO_GRADE], bytes(bots.INFO_GRADE - 57))
                self.assertEqual(info[0][bots.INFO_GRADE], 0xFF)  # 0 virava patente de GM nos outros
            await self.cmd('/bot remove')

    async def test_confirms_result_screen(self):
        """Na tela de resultado o bot manda o 0x8103 (OK), senão o humano fica esperando os outros usuários."""
        await self.cmd('/bot add')
        self.master.sent.clear()
        await bots.confirm_result(self.room, 0)
        from tools.tunnel_decode import decode, key
        plains = [decode(raw[3:], key(self.master.server.index, self.room.id))[2]
                  for raw in self.master.sent if raw[:2] == bytes([0x01, 0x45])]
        self.assertEqual([p[:2] for p in plains], [struct.pack('<H', bots.RESULT_OK)])

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
