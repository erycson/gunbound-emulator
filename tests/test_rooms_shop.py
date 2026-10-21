"""
Testes das regras de sala/partida/loja sem rede nem banco (conexões e repositórios falsos).
Uso (na pasta do servidor): python -m unittest tests.test_rooms_shop -v
"""
import asyncio
import struct
import time
import unittest
from gunbound.base.enums import RoomOptions, RoomMode, RoomStatus, AcquisitionType
from gunbound.game.room import Room
from gunbound.game.channel import Channel
from gunbound.game.managers.rooms import RoomManager
from gunbound.game.managers.client import ClientManager
from gunbound.game.protocol.enums import ServerPacket, ServerCode
from gunbound.game.protocol.base import Packet
from gunbound.util import BinaryReader


class FakeServer:
    id = 1
    config = {'product_version': 440}


class FakeConn:
    _next = 1

    def __init__(self, nick, authority=0):
        FakeConn._next += 1
        self.id = FakeConn._next
        self.addr = f"127.0.0.1:{self.id}"
        self.server = FakeServer()
        self.closing = False
        self.room = None
        self.sent: list[bytes] = []
        self.data = {'profile': {'Id': nick, 'Nickname': nick, 'Gender': 0, 'Authority': authority},
                     'game': {'Guild': '', 'TotalGrade': 1, 'SeasonGrade': 1, 'Money': 0, 'ClientData': b'\x00' * 4}}

    async def on_send(self, packet):
        self.sent.append(packet.buf.getvalue())

    async def close(self):
        self.closing = True

    def cmds(self) -> list[int]:
        return [struct.unpack_from('<H', b)[0] for b in self.sent]

    def last(self, cmd) -> bytes:
        return next(b for b in reversed(self.sent) if struct.unpack_from('<H', b)[0] == cmd)


def manager() -> RoomManager:
    return RoomManager(server=None, config={'announcement': 'oi'}, room_factory=lambda **kw: Room(**kw))


async def settle():
    for _ in range(5):
        await asyncio.sleep(0)


class RoomRulesTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rooms = manager()
        self.master = FakeConn('master')
        self.room = await self.rooms.create(self.master, RoomOptions('sala', RoomMode.SOLO, 2, 'abc'))

    async def test_full_room(self):
        b, c = FakeConn('b'), FakeConn('c')
        self.assertEqual(self.room.can_join(b, 'abc'), ServerCode.SRV_OK)
        await self.room.join(b)
        self.assertEqual(self.room.can_join(c, 'abc'), ServerCode.SRV_ROOM_FULL)
        self.assertIsNone(await self.room.join(c))

    async def test_wrong_password_and_in_game(self):
        b = FakeConn('b')
        self.assertEqual(self.room.can_join(b, 'zzz'), ServerCode.SRV_WRONG_PASSWORD)
        self.room.status = RoomStatus.IN_GAME
        self.assertEqual(self.room.can_join(b, 'abc'), ServerCode.SRV_ROOM_IN_GAME)

    async def test_start_rules(self):
        b = FakeConn('b')
        self.assertEqual(self.room.start_check(self.master), "jogadores insuficientes")
        await self.room.join(b)
        self.assertEqual(self.room.start_check(b), "só o mestre inicia")
        self.assertEqual(self.room.start_check(self.master), "nem todos estão prontos")
        self.room.set_ready(b, True)
        self.assertIsNone(self.room.start_check(self.master))  # 1x1, times A/B
        self.assertFalse(self.room.set_ready(self.master, True))  # mestre não usa pronto

    async def test_unbalanced_teams(self):
        self.room.options.size = 4
        b = FakeConn('b')
        await self.room.join(b)
        self.assertTrue(self.room.set_team(b, 0))
        self.room.set_ready(b, True)
        self.assertIn("desbalanceados", self.room.start_check(self.master))

    async def test_gm_can_start_alone(self):
        gm = FakeConn('gm', authority=99)
        room = await self.rooms.create(gm, RoomOptions('gm', RoomMode.SOLO, 2, None))
        self.assertIsNone(room.start_check(gm))

    async def test_leave_moves_master_and_notifies(self):
        b = FakeConn('b')
        await self.room.join(b)
        await self.rooms.leave(self.master)
        await settle()
        self.assertIs(self.room.owner, b)
        self.assertIn(ServerPacket.SRV_ROOM_PLAYER_LEAVE, b.cmds())
        self.assertIn(ServerPacket.SRV_ROOM_HOST_CHANGE, b.cmds())
        await self.rooms.leave(b)
        self.assertIsNone(self.rooms.get(self.room.id))  # sala vazia destruída

    async def test_kick(self):
        b = FakeConn('b')
        await self.room.join(b)
        self.assertIsNone(await self.room.kick(b, 0))            # não mestre
        self.assertIsNone(await self.room.kick(self.master, 0))  # a si mesmo
        self.assertIsNotNone(await self.room.kick(self.master, 1))
        self.assertIsNone(b.room)

    async def test_elimination_winner(self):
        b = FakeConn('b')
        await self.room.join(b)
        self.room.players[b.id].team = 1
        self.room.start()
        self.assertEqual(self.room.on_dead(b), 0)
        self.assertEqual(self.room.on_dead(b), -1)  # morte repetida ignorada

    async def test_spawn_from_stage_table(self):
        # WCS1: tabela de 2007 (mapa,lado,vaga,Y,x_min,x_max). Nirvana B (mapa 2, lado 1) tem Y nas vagas 1..6
        b = FakeConn('b')
        await self.room.join(b)
        self.room.players[b.id].team = 1
        self.room.options.map = 2
        self.room.options.settings = (self.room.options.settings & ~0x300FF) | 1 << 16 | 0x80  # lado B, EvsW
        game = self.room.start()
        spawns = [game.spawn_of(p.slot) for p in self.room.sorted_players()]
        ranges = {(469, 564), (829, 916), (1101, 1206), (634, 716), (920, 1017), (569, 630), (752, 824), (1021, 1097)}
        self.assertTrue(all(y > 0 and any(lo <= x <= hi for lo, hi in ranges) for x, y in spawns), spawns)

    async def test_score_lives_and_resurrect(self):
        room = await self.rooms.create(FakeConn('m2'), RoomOptions('s', RoomMode.SCORE, 2, None))
        b = FakeConn('b')
        await room.join(b)
        room.start()
        self.assertEqual(room.on_dead(b), -1)       # ainda tem vida
        self.assertTrue(room.on_resurrect(b))
        self.assertEqual(room.on_dead(b), 0)        # acabou a vida do time B

    async def test_capacity_cannot_drop_below_players(self):
        from gunbound.game.protocol.room_settings import RoomChangeMaxMenRecv
        self.room.options.size = 4
        await self.room.join(FakeConn('b'))
        await self.room.join(FakeConn('c'))
        h = RoomChangeMaxMenRecv(self.master, BinaryReader(bytes([2])))
        await h.process()
        self.assertEqual(self.room.options.size, 4)


class LobbyLiveTest(unittest.IsolatedAsyncioTestCase):
    """0x21F0..0x21F7: lista de salas ao vivo para quem está no canal sem sala."""

    async def asyncSetUp(self):
        from gunbound.game.channel import Channel
        self.rooms, self.channel = manager(), Channel(None, 0)
        self.lobby, self.master = FakeConn('lobby'), FakeConn('m')
        for c in (self.lobby, self.master):
            c.channel = self.channel
            await self.channel.add(c)
        self.rooms.watch(self.lobby, [0])  # listou o id 0 vazio pelo 0x2101: recebe o 0x21F0 da sala nova
        self.room = await self.rooms.create(self.master, RoomOptions('sala', RoomMode.SOLO, 2, None))
        await settle()

    def body(self, cmd) -> bytes:
        return self.lobby.last(cmd)[2:]

    async def test_created_matches_list_entry(self):
        from gunbound.game import room_packets as rp
        entry = rp.room_list([self.room]).buf.getvalue()[2 + 2 + 2:-1]  # cmd, rtc, contagem ... 00 final
        created = self.body(ServerPacket.SRV_LOBBY_ROOM_CREATED)
        self.assertEqual(entry[:-4], created[:-4] + b'\x00')  # o 0x2103 do WC tem um byte a mais antes dos 4 finais
        self.assertEqual(entry[-4:], created[-4:])
        self.assertNotIn(ServerPacket.SRV_LOBBY_ROOM_CREATED, self.master.cmds())  # já está na sala

    async def test_only_recent_list_viewers(self):
        from gunbound.game.managers.rooms import LOBBY_WATCH_SECONDS
        idle, old, other = FakeConn('idle'), FakeConn('old'), FakeConn('other')  # nunca listou / listou há > 30 s / outra sala
        self.rooms.watch(old, [self.room.id])
        self.rooms.watchers[self.room.id][old] -= LOBBY_WATCH_SECONDS + 1
        self.rooms.watch(other, [self.room.id + 1])
        self.rooms.watch(self.lobby, [self.room.id])
        await self.rooms.leave(self.master)
        await settle()
        self.assertIn(ServerPacket.SRV_LOBBY_ROOM_DESTROYED, self.lobby.cmds())
        self.assertEqual((idle.cmds(), old.cmds(), other.cmds()), ([], [], []))

    async def test_list_by_id_and_auto_rooms(self):
        from gunbound.game.protocol.room_sorted_list import RoomListByIdRecv, RoomSortedListRecv
        quick = await self.rooms.create(FakeConn('q'), RoomOptions('q', RoomMode.SOLO, 2, None), auto=True)
        await RoomListByIdRecv(self.lobby, BinaryReader(struct.pack("<3H", self.room.id, 40, quick.id))).handle(rooms=self.rooms)
        body = self.lobby.last(ServerPacket.SRV_ROOM_SORTED_LIST)[2:]
        self.assertEqual(struct.unpack_from('<HHH', body), (0, 3, self.room.id))
        self.assertTrue(body.endswith(struct.pack('<HB', 40, 0) + struct.pack('<HB', quick.id, 0) + b'\x00'))
        self.assertEqual(self.lobby.data['room_watch'], (self.room.id, 40, quick.id))
        await RoomSortedListRecv(self.lobby, BinaryReader(struct.pack("<BHH", 1, 0, 6))).handle(rooms=self.rooms)
        self.assertEqual(struct.unpack_from("<HH", self.lobby.last(ServerPacket.SRV_ROOM_SORTED_LIST), 2), (0, 1))  # sem a automática
        self.assertEqual(self.lobby.data['room_watch'], (self.room.id,))

    async def test_join_leave_destroy(self):
        b = FakeConn('b')
        b.channel = self.channel
        from gunbound.game.protocol.room_join import enter_room
        await enter_room(b, self.room, '', ServerPacket.SRV_ROOM_JOIN)
        await settle()
        self.assertEqual(self.body(ServerPacket.SRV_LOBBY_ROOM_PLAYERS), struct.pack('<HB', self.room.id, 2))
        await self.rooms.leave(b)
        await settle()
        self.assertEqual(self.body(ServerPacket.SRV_LOBBY_ROOM_PLAYERS), struct.pack('<HB', self.room.id, 1))
        await self.rooms.leave(self.master)
        await settle()
        self.assertEqual(self.body(ServerPacket.SRV_LOBBY_ROOM_DESTROYED), struct.pack('<H', self.room.id))
        self.assertNotIn(ServerPacket.SRV_LOBBY_ROOM_DESTROYED, self.master.cmds())  # não listou a sala

    async def test_event_command_keeps_mode(self):
        from gunbound.game.protocol.room_settings import RoomChangeOptionRecv, RoomChangeStageRecv
        self.room.options.mode = RoomMode.SCORE
        # /<evento> do cliente: (settings & 0xFFFFF) | evento << 24 apaga o bit 22 do Score; o original grava cru
        event = ((0x44 << 16) & 0xFFFFF) | 1 << 24 | 2
        await RoomChangeOptionRecv(self.master, BinaryReader(struct.pack('<I', event))).process()
        self.assertEqual((self.room.options.mode, self.room.options.settings), (RoomMode.SCORE, event))
        # WCS1: tabela de 2007, com os lados C/D
        await RoomChangeOptionRecv(self.master, BinaryReader(struct.pack('<I', event | 3 << 16))).process()
        self.assertEqual(self.room.options.settings, event | 3 << 16)
        self.room.options.settings = event
        # mapa sem vaga na tabela: recusa (0x406700) sem derrubar
        await RoomChangeStageRecv(self.master, BinaryReader(bytes([19]))).process()
        self.assertEqual((self.room.options.settings, self.room.options.map, self.master.closing), (event, 0, False))
        # posições >= 3 ou mapa >= 20: o original derruba a conexão (handler devolve falso)
        await RoomChangeOptionRecv(self.master, BinaryReader(struct.pack('<I', event | 5))).process()
        self.assertEqual((self.room.options.settings, self.master.closing), (event, True))
        self.master.closing = False
        await RoomChangeStageRecv(self.master, BinaryReader(bytes([20]))).process()
        self.assertTrue(self.master.closing)

    async def test_score_lives_and_random_stage(self):
        self.room.options.mode = RoomMode.SCORE
        self.room.options.settings |= 0xF00000
        previous = 0
        for _ in range(60):
            stage = self.room._random_stage()
            self.assertTrue(stage == 0 or (1 <= stage <= 10 and stage != previous))
            self.assertIn(self.room.options.side, (0, 1))
            previous = stage or previous
        game = self.room.start()
        lives = len(self.room.sorted_players()) // 2 + 1
        self.assertEqual(((self.room.options.settings >> 20) & 0xF, set(game.score.values())), (lives, {lives}))

    async def test_state_and_settings(self):
        from gunbound.game.protocol.room_settings import RoomChangeTitleRecv, RoomChangeStageRecv, RoomChangeMaxMenRecv
        await RoomChangeTitleRecv(self.master, BinaryReader(b'novo\x00')).process()
        await RoomChangeStageRecv(self.master, BinaryReader(bytes([3]))).process()
        await RoomChangeMaxMenRecv(self.master, BinaryReader(bytes([4]))).process()
        self.room.start()
        await settle()
        self.assertEqual(self.body(ServerPacket.SRV_LOBBY_ROOM_STATE), struct.pack('<HB', self.room.id, 1))
        self.room.finish()
        await settle()
        rid = struct.pack('<H', self.room.id)
        self.assertEqual(self.body(ServerPacket.SRV_LOBBY_ROOM_STATE), rid + b'\x00')
        self.assertEqual(self.body(ServerPacket.SRV_LOBBY_ROOM_TITLE), rid + b'novo')
        self.assertEqual(self.body(ServerPacket.SRV_LOBBY_ROOM_MAP), rid + b'\x03')
        self.assertEqual(self.body(ServerPacket.SRV_LOBBY_ROOM_MAXMEN), rid + b'\x04')

    async def test_grandprix_room_is_silent(self):
        await self.rooms.create(FakeConn('gp'), RoomOptions('gp', RoomMode.SOLO, 2, None), grandprix=(0, 0))
        before = len(self.lobby.sent)
        gp = FakeConn('gp2')
        gp.channel = self.channel
        await self.rooms.create(gp, RoomOptions('gp', RoomMode.SOLO, 2, None), grandprix=(0, 0))
        await settle()
        self.assertEqual(len(self.lobby.sent), before)


class HandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_join_packets(self):
        from gunbound.game.protocol.room_create import RoomCreateRecv
        from gunbound.game.protocol.room_join import RoomJoinRecv
        rooms = manager()
        a, b = FakeConn('a'), FakeConn('b')
        a.channel = b.channel = Channel(None, 0)
        body = bytes([4]) + b'sala' + bytes.fromhex('b2620c00') + b'1234' + bytes([8])
        a.server.config['stage_event'] = 3
        await RoomCreateRecv(a, BinaryReader(body)).handle(rooms=rooms)
        self.assertEqual(a.cmds(), [ServerPacket.SRV_ROOM_CREATE])
        room = a.room
        self.assertEqual((room.options.mode, room.options.size, room.options.password), (RoomMode.JEWEL, 8, '1234'))
        self.assertEqual(room.options.settings >> 24, 3)  # StageEvent << 24 na criação

        await RoomJoinRecv(b, BinaryReader(struct.pack('<H', room.id) + b'errada\x00')).handle(rooms=rooms)
        self.assertEqual(struct.unpack_from('<H', b.last(ServerPacket.SRV_ROOM_JOIN), 2)[0], ServerCode.SRV_WRONG_PASSWORD)
        await RoomJoinRecv(b, BinaryReader(struct.pack('<H', room.id) + b'1234\x00')).handle(rooms=rooms)
        await settle()
        self.assertEqual(b.cmds()[-1], ServerPacket.SRV_ROOM_JOIN)
        self.assertIn(ServerPacket.SRV_ROOM_PLAYER_JOIN, a.cmds())

    async def test_short_packet_raises_packet_error(self):
        from gunbound.game.protocol.room_create import RoomCreateRecv
        from gunbound.util.binary_buffer import PacketError
        a = FakeConn('a'); a.channel = Channel(None, 0)
        with self.assertRaises(PacketError):
            await RoomCreateRecv(a, BinaryReader(bytes([10]) + b'abc')).handle(rooms=manager())

    async def test_tunnel_only_to_same_room(self):
        from gunbound.game.protocol.game_play import GameTunnelRecv
        rooms = manager()
        a, b = FakeConn('a'), FakeConn('b')
        room = await rooms.create(a, RoomOptions('t', RoomMode.SOLO, 2, None))
        await room.join(b)
        await GameTunnelRecv(a, BinaryReader(b'\x02\x00\x00\x01dados')).process()
        self.assertEqual(b.last(ServerPacket.SRV_GAME_TUNNEL)[2:], b'\x00dados')
        self.assertEqual(a.last(ServerPacket.SRV_GAME_TUNNEL)[2:], b'\x00dados')  # remetente listado também recebe

    def test_local_udp_fix(self):
        from unittest import mock
        from gunbound.game import room_packets as rp
        a = FakeConn('a')
        a.data['net'] = (0x0100007F, 8363)
        self.assertEqual(rp.player_net(a)[1], 8363)  # desligado: a porta informada no login
        a.server = type('S', (FakeServer,), {'config': {**FakeServer.config, 'local_udp_fix': True}})()
        with mock.patch.object(rp, 'real_udp_port', return_value=50000):
            self.assertEqual(rp.player_net(a)[1], 50000)

    async def test_tunnel_log(self):
        import json, os, tempfile
        from gunbound.game.protocol.game_play import GameTunnelRecv
        rooms = manager()
        a, b = FakeConn('a'), FakeConn('b')
        room = await rooms.create(a, RoomOptions('t', RoomMode.SOLO, 2, None))
        await room.join(b)
        path = os.path.join(tempfile.mkdtemp(), 'tunnel.jsonl')
        a.server = type('S', (FakeServer,), {'config': {**FakeServer.config, 'tunnel_log': path}})()
        await GameTunnelRecv(a, BinaryReader(b'\x01\x00\x01dados')).process()
        with open(path, encoding='utf-8') as f:
            line = json.loads(f.readline())
        self.assertEqual((line['from'], line['to'], line['hex'], line['nick']), (0, [1], b'dados'.hex(), 'a'))


class SessionTest(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_login_kicks_old_session(self):
        mgr = ClientManager(client_factory=None)
        old, new = FakeConn('test'), FakeConn('test')
        await mgr.claim_session('test', old)
        await mgr.claim_session('test', new)
        self.assertTrue(old.closing)
        self.assertIs(mgr.get_session('test'), new)
        mgr.release_session('test', old)            # close atrasado da antiga não apaga a nova
        self.assertIs(mgr.get_session('test'), new)


class FakeInventory:
    def __init__(self, money):
        self.money, self.bought = money, False

    async def get_menu(self, *a):
        return {'PriceByGoldForI': 500}

    async def get_money(self, user_id):
        return self.money

    async def get_cash(self, user_id):
        return 0

    async def update_wearing(self, user_id, changes):
        self.wearing = changes


class ShopTest(unittest.IsolatedAsyncioTestCase):
    async def test_buy_without_gold_does_nothing(self):
        from gunbound.game.protocol.item_buy import ItemBuyRecv
        conn = FakeConn('pobre')
        plain = struct.pack('<iIBB', (0x6020 + 0x8631607E) & 0x7FFFFFFF, 1, 1, 7) + b'\x00' * 6
        conn.decrypt = lambda data: data
        inv = FakeInventory(money=100)

        class NoDb:
            async def transaction(self):
                raise AssertionError("não deveria abrir transação sem saldo")

        h = ItemBuyRecv(conn, BinaryReader(plain), db=NoDb(), config={}, inventory_repository=inv)
        await h.process()
        self.assertEqual(conn.sent, [])
        self.assertEqual((AcquisitionType.try_parse_int(0), AcquisitionType.try_parse_int(1)), (AcquisitionType.Gold, AcquisitionType.Cash))


    async def test_item_wear_real_client_body(self):
        from gunbound.game.protocol.misc import AvatarSaveRecv
        conn = FakeConn('a')
        conn.data.setdefault('profile', {'Id': 1})
        inv = FakeInventory(0)
        async def chest(uid):
            return [{'No': 3, 'Item': 300, 'Expire': None}, {'No': 4, 'Item': 400, 'Expire': None}]
        inv.get_chest = chest
        h = AvatarSaveRecv(conn, BinaryReader(bytes.fromhex('0200030000000104000000 01'.replace(' ', ''))))
        h.user_id = lambda: 1
        await h.handle(inventory_repository=inv)
        self.assertEqual(struct.unpack_from('<H', conn.last(ServerPacket.SRV_ITEM_WEAR), 2)[0], 0)
        self.assertEqual(conn.data['avatar'], [300, 400])


if __name__ == '__main__':
    unittest.main()


class RoomLeaveTest(unittest.IsolatedAsyncioTestCase):
    """0x3001: sai da sala e reentra no canal atual (-1) com 0x2001, como o original (0x429626)."""

    async def test_leave_rejoins_channel(self):
        from gunbound.game.protocol.room_join import RoomLeaveRecv
        channel, other = Channel(None, 0), Channel(None, 1)
        master, lobby = FakeConn('m'), FakeConn('l')
        for c in (master, lobby):
            c.data['game'].update(CountryGrade=0, Country=0)
            c.server = type('S', (), {'id': 1, 'config': {'announcement': 'oi'}})()
            c.channel = channel
            await channel.add(c)
        rooms = manager()
        await rooms.create(master, RoomOptions('sala', RoomMode.SOLO, 2, None))

        class Channels:
            def get(self, i): return {0: channel, 1: other}[i]
            def get_least_populated(self): return other

        room = master.room
        await RoomLeaveRecv(master, BinaryReader(struct.pack('<h', 9))).handle(rooms=rooms, channels=Channels())
        self.assertEqual((master.last(ServerPacket.SRV_CHANNEL_JOIN)[2:4], master.room), (b'\x1d\x00', room))  # fica na sala
        await RoomLeaveRecv(master, BinaryReader(b'\xff\xff')).handle(rooms=rooms, channels=Channels())
        await settle()
        self.assertIsNone(master.room)
        self.assertIs(master.channel, channel)
        self.assertEqual(struct.unpack_from('<HH', master.last(ServerPacket.SRV_CHANNEL_JOIN), 0), (ServerPacket.SRV_CHANNEL_JOIN, 0))
        self.assertIn(ServerPacket.SRV_CHANNEL_JOIN_UPDATE, lobby.cmds())
        # fora de sala (ou sala em jogo): 0x2001 RTC 0x2009, sem mexer no canal
        await RoomLeaveRecv(master, BinaryReader(b'\xff\xff')).handle(rooms=rooms, channels=Channels())
        self.assertEqual(master.last(ServerPacket.SRV_CHANNEL_JOIN)[2:4], b'\x09\x20')
        self.assertIs(master.channel, channel)


class TurnOrderTest(unittest.IsolatedAsyncioTestCase):
    """Original (2006 0x415b40 / 2007 0x418be0): ordem por TotalGrade e times da QuickStartRoom pela patente."""

    async def test_alternate_weakest_first(self):
        import random
        from gunbound.game.room import RoomPlayer, turn_order
        def p(slot, team, grade):
            c = FakeConn(f'p{slot}')
            c.data['game']['TotalGrade'] = grade
            return RoomPlayer(c, slot=slot, team=team)
        players = [p(0, 0, 5), p(1, 1, 3), p(2, 0, 10), p(3, 1, 12)]
        orders = {tuple(turn_order(players, random.Random(s))) for s in range(20)}
        self.assertEqual(orders, {(2, 3, 0, 1), (3, 2, 1, 0)})  # mais fraco (grade maior) primeiro, times alternados

    async def test_quick_teams_and_full_room(self):
        from gunbound.game.protocol.room_join import RoomQuickStartRecv
        rooms = manager()
        rooms.quick_min_players = 4
        conns = [FakeConn(n) for n in 'abcd']
        for c, grade in zip(conns, (9, 2, 15, 5)):
            c.data['game']['TotalGrade'] = grade
            await RoomQuickStartRecv(c, BinaryReader(b'')).handle(rooms=rooms)
        room = conns[0].room
        self.assertTrue(all(c.room is room for c in conns))
        self.assertIsNone(room.start_check(conns[0]))   # sem "pronto" na QuickStartRoom
        # por patente: b(2) A, d(5) B, a(9) B, c(15) A
        self.assertEqual([room.player(c).team for c in conns], [1, 0, 0, 1])
        await room.leave(conns[2])
        await room.leave(conns[3])
        self.assertEqual(room.start_check(conns[0]), "QuickStartRoom incompleta")  # 2006: total == QuickStartMan


class IdleRoomTest(unittest.IsolatedAsyncioTestCase):
    """L8: sala ociosa (original 2006/2007): aviso 0x5101 a partir de warn, fecha com 0x3FFF depois de close."""

    async def test_warn_then_close(self):
        rooms = manager()
        rooms.config['idle_room'] = {'close_msg': 'fechada', 'warn_msg': 'aviso'}
        a, b = FakeConn('a'), FakeConn('b')
        room = await rooms.create(a, RoomOptions('sala', RoomMode.SOLO, 4, None))
        await room.join(b)
        t0 = room.idle_since
        await rooms.check_idle(True, t0 + 1139)
        self.assertNotIn(ServerPacket.SRV_COMMAND, b.cmds())
        await rooms.check_idle(True, t0 + 1140)
        await settle()
        self.assertEqual(b.last(ServerPacket.SRV_COMMAND)[2:], b'aviso')
        room.start()
        await rooms.check_idle(True, t0 + 5000)   # 2006: só salas aguardando
        self.assertIs(a.room, room)
        await rooms.check_idle(False, t0 + 5000)  # sem o filtro: todas
        await settle()
        self.assertEqual((a.room, b.room, b.last(ServerPacket.SRV_ROOM_KICKED)[2:]), (None, None, b'fechada'))
        self.assertIsNone(rooms.get(room.id))


class HiddenTankTest(unittest.TestCase):
    def test_ratio_and_authority(self):
        import random
        from gunbound.game.room import roll_tank, HIDDEN_TANKS
        from gunbound.game.protocol.room_select_tank import valid_tank
        rng = random.Random(1)
        rolls = [roll_tank(0xFF, rng, 20) for _ in range(5000)]
        hidden = sum(r in HIDDEN_TANKS for r in rolls) / len(rolls)
        self.assertTrue(0.17 < hidden < 0.23 and all(r < 16 or r in HIDDEN_TANKS for r in rolls))
        self.assertEqual(roll_tank(3, rng), 3)
        self.assertEqual((valid_tank(0x11), valid_tank(0x11, 98), valid_tank(0x13, 100)), (False, True, False))

    def test_tanks_per_phase(self):
        import random
        from gunbound.game import phase
        from gunbound.game.room import roll_tank
        from gunbound.game.protocol.room_select_tank import valid_tank
        th, s1, s2 = (phase.load(n) for n in ('TH', 'WCS1', 'WCS2'))
        # 0x10 BigFoot MkII só do S1 em diante; 0x13..0x18 só no S2; 0x12 não existe fora do oculto de GM
        self.assertEqual([valid_tank(0x10, 0, p.tanks) for p in (th, s1, s2)], [False, False, False])  # v584: -1
        self.assertEqual([valid_tank(0x18, 0, p.tanks) for p in (th, s1, s2)], [False, False, True])
        self.assertEqual((valid_tank(0x12, 0, s2.tanks), valid_tank(0x12, 98, s2.tanks)), (False, True))
        rng = random.Random(2)
        self.assertEqual({roll_tank(0xFF, rng, 0, th.random_tanks) for _ in range(500)}, set(range(16)))
        self.assertEqual({roll_tank(0xFF, rng, 0, s2.random_tanks) for _ in range(2000)}, set(s2.tanks))
