"""
Serviços extraídos do original (console admin, denúncia, baú, drop, nick). Conexões e repositórios falsos.
Uso: python -m unittest tests.test_services -v
"""
import struct
import unittest
from gunbound.base.enums import RoomOptions, RoomMode
from gunbound.game.protocol import admin_console as ac
from gunbound.game.protocol import services as sv
from gunbound.game.protocol.base import CRYPT_MAGIC
from gunbound.game.protocol.enums import ClientPacket, ServerPacket
from gunbound.util import BinaryReader
from tests.test_gm import FakeClients, conn
from tests.test_rooms_shop import manager


def crypt_conn(nick, authority=0):
    c = conn(nick, authority)
    c.get_derived_key = lambda: b'k'
    c.decrypt = lambda data: data  # corpo "cifrado" = texto puro nos testes
    c.server.config = {'host': '127.0.0.1', 'port': 8360, 'grade_min': 19, 'grade_max': -4, 'version_min': 440,
                       'version_max': 440, 'gold_factor': 230, 'score_factor': 270, 'announcement': 'oi'}
    return c


def blocks(cmd: int, data: bytes) -> bytes:
    data += b'\x00' * (-len(data) % 12)
    prefix = struct.pack('<I', (cmd - CRYPT_MAGIC) & 0xFFFFFFFF)
    return b''.join(prefix + data[i:i + 12] for i in range(0, len(data), 12))


class FakeRepo:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        async def fn(*args):
            self.calls.append((name, args))
            return self.results.get(name)
        return fn


def repo(**results):
    r = FakeRepo()
    r.results = results
    return r


class AdminConsoleTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rooms = manager()
        self.admin, self.user = crypt_conn('adm', 100), crypt_conn('u', 1)
        self.user.server = self.admin.server
        self.clients = FakeClients(self.admin, self.user)

    async def run_cmd(self, cmd, c, body=b''):
        from gunbound.base.protocol import BasePackageFactory as F
        await F.registry[cmd](c, BinaryReader(body)).handle(clients=self.clients, rooms=self.rooms)

    async def test_no_authority_no_reply(self):
        await self.run_cmd(ClientPacket.CLI_CMD_SET_FACTOR, self.user, struct.pack('<II', 1, 2))
        self.assertEqual(self.user.sent, [])
        self.assertEqual(self.admin.server.config['gold_factor'], 230)

    async def test_set_factor_and_status(self):
        await self.run_cmd(ClientPacket.CLI_CMD_SET_FACTOR, self.admin, struct.pack('<II', 300, 250))
        self.assertEqual(self.admin.last(ServerPacket.SRV_CMD_SET_FACTOR)[2:], b'\x00\x00')
        await self.run_cmd(ClientPacket.CLI_CMD_STATUS, self.admin)
        status = self.admin.last(ServerPacket.SRV_CMD_STATUS)
        self.assertEqual(struct.unpack_from('<II', status, len(status) - 8), (300, 250))

    async def test_function_restrict_mask(self):
        self.admin.server.config['function_restrict'] = 0b1010
        await self.run_cmd(ClientPacket.CLI_CMD_FUNCTION_RESTRICT, self.admin, struct.pack('<II', 0b0011, 0b0001))
        self.assertEqual(self.admin.server.config['function_restrict'], 0b1001)

    async def test_event_prob_sets_flag(self):
        await self.run_cmd(ClientPacket.CLI_CMD_SET_EVENTACTPROB, self.admin, struct.pack('<HHBB', 1, 50, 2, 3))
        self.assertTrue(self.admin.server.config['function_restrict'] & (ac.EVENT_FLAG << 1))
        await self.run_cmd(ClientPacket.CLI_CMD_SET_EVENTACTPROB, self.admin, struct.pack('<HHBB', 1, 0, 0, 0))
        self.assertFalse(self.admin.server.config['function_restrict'] & (ac.EVENT_FLAG << 1))

    async def test_motd_and_bcm(self):
        await self.run_cmd(ClientPacket.CLI_CMD_MOTD, self.admin, b'\x02sala nova\x00')
        self.assertEqual(self.rooms.motd(), 'sala nova')
        await self.run_cmd(ClientPacket.CLI_CMD_BCM, self.admin, b'\x00aviso\x00')
        self.assertEqual(self.user.last(ServerPacket.SRV_COMMAND)[2:], b'aviso')

    async def test_set_version(self):  # original: estreitar a faixa derruba todos (inclusive o admin) sem resposta
        await self.run_cmd(ClientPacket.CLI_CMD_SETVERSION, self.admin, struct.pack('<II', 400, 500))
        self.assertEqual(self.admin.last(ServerPacket.SRV_CMD_SETVERSION)[2:], b'\x00\x00')
        self.assertFalse(self.user.closing)
        await self.run_cmd(ClientPacket.CLI_CMD_SETVERSION, self.admin, struct.pack('<II', 440, 500))
        self.assertTrue(self.admin.closing and self.user.closing)
        self.assertEqual(self.admin.server.config['version_min'], 440)

    async def test_allowed_guild_too_long(self):
        await self.run_cmd(ClientPacket.CLI_CMD_SET_ALLOWEDGUILD, self.admin, struct.pack('<H', 0x50) + b'x' * 0x50)
        self.assertEqual(self.admin.last(ServerPacket.SRV_CMD_SET_ALLOWEDGUILD)[2:], b'\x1b\x00')
        body = struct.pack('<H', 2) + b'abc'.ljust(8, b'\x00') + b'guilda12'
        await self.run_cmd(ClientPacket.CLI_CMD_SET_ALLOWEDGUILD, self.admin, body)
        self.assertEqual(self.admin.server.config['allowed_guild'], ['abc', 'guilda12'])  # u16 n + n x char[8]

    async def test_monitor(self):
        await ac.ChannelMonitorRecv(self.user, BinaryReader(b'')).handle()
        self.assertNotIn(self.user, ac.monitors)
        await ac.ChannelMonitorRecv(self.admin, BinaryReader(b'')).handle()
        self.assertIn(self.admin, ac.monitors)
        await ac.ChannelMonitorStopRecv(self.admin, BinaryReader(b'')).handle()
        self.assertNotIn(self.admin, ac.monitors)


class ServicesTest(unittest.IsolatedAsyncioTestCase):
    async def test_accuse(self):
        c = crypt_conn('a')
        body = b'vilao'.ljust(16, b'\x00') + b'\x05xinga' + struct.pack('<H', 3) + b'log'
        r = sv.PoliceAccuseRecv(c, BinaryReader(blocks(0x5000, body)))
        repo_ = repo()
        await r.handle(server_repository=repo_)
        self.assertEqual(repo_.calls[0][1][3:], ('vilao', 'xinga\nlog'))
        self.assertIn(ServerPacket.SRV_POLICE_ACCUSE, c.cmds())

    async def test_item_location_exact_size(self):
        c = crypt_conn('a')
        repo_ = repo()
        await sv.ItemLocationRecv(c, BinaryReader(struct.pack('<HII', 1, 7, 3))).handle(inventory_repository=repo_)
        self.assertEqual(repo_.calls[0][1], ('a', [(7, 3)]))
        repo_.calls.clear()
        await sv.ItemLocationRecv(c, BinaryReader(struct.pack('<HI', 1, 7))).handle(inventory_repository=repo_)
        self.assertEqual(repo_.calls, [])

    async def test_gift_needs_own_item(self):
        c = crypt_conn('a')
        body = struct.pack('<I', 9) + b'b'.ljust(16, b'\x00') + b'Bee'.ljust(12, b'\x00') + b'\x02oi'  # chest, Id16, Nick12
        inv = repo(transfer_chest=None)
        await sv.ItemGiftRecv(c, BinaryReader(blocks(0x6028, body))).handle(inventory_repository=inv, user_repository=repo(get_profile={'Id': 'b'}))
        self.assertEqual(c.last(ServerPacket.SRV_ITEM_GIFT)[2:], b'\x04\x00')
        c.server.config['super_user_item'] = 204801
        c.data['power_user'] = True
        inv = repo(transfer_chest=204801)
        await sv.ItemGiftRecv(c, BinaryReader(blocks(0x6028, body))).handle(inventory_repository=inv, user_repository=repo(get_profile={'Id': 'b'}))
        self.assertEqual(inv.calls[0][1], (9, 'a', 'b', 'Bee', 'oi'))
        self.assertEqual(c.last(ServerPacket.SRV_ITEM_GIFT)[2:], b'\x00\x00')
        self.assertFalse(c.data['power_user'])

    async def test_gift_prohibit_time_drops(self):
        from datetime import datetime, timedelta
        c = crypt_conn('a')
        c.data['game'] = {'GiftProhibitTime': datetime.now() + timedelta(hours=1)}
        body = struct.pack('<I', 9) + b'b'.ljust(16, b'\x00') + b'Bee'.ljust(12, b'\x00') + b'\x02oi'
        inv = repo(transfer_chest=1)
        await sv.ItemGiftRecv(c, BinaryReader(blocks(0x6028, body))).handle(inventory_repository=inv, user_repository=repo(get_profile={'Id': 'b'}))
        self.assertEqual(inv.calls, [])
        self.assertNotIn(ServerPacket.SRV_ITEM_GIFT, c.cmds())
        self.assertTrue(c.closing)

    async def test_user_nick(self):
        c = crypt_conn('a')
        users = repo(get_nicknames=[{'Id': 'b', 'Nickname': 'Bee'}])
        await sv.UserNickRecv(c, BinaryReader(struct.pack('<H', 1) + b'b'.ljust(16, b'\x00'))).handle(user_repository=users)
        out = c.last(ServerPacket.SRV_USER_NICK)
        self.assertEqual(out[2:4], b'\x01\x00')
        self.assertEqual(out[4:20].rstrip(b'\x00'), b'b')
        self.assertEqual(out[20:32].rstrip(b'\x00'), b'Bee')

    async def test_drop_user(self):
        rooms = manager()
        a, b = crypt_conn('a'), crypt_conn('b')
        room = await rooms.create(a, RoomOptions('t', RoomMode.SOLO, 2, None))
        await room.join(b)
        await sv.PlayDropUserRecv(a, BinaryReader(blocks(0x4000, b'\x01'))).handle()
        self.assertIn(ServerPacket.SRV_PLAY_DROP_USER, b.cmds())


class ReadStringTest(unittest.TestCase):
    def test_lixo_depois_do_nul(self):
        # 0x1020 real do TH v404: "test", NUL e lixo de memória no resto dos 12 bytes
        r = BinaryReader(bytes.fromhex('0100 74657374 00000000 8C7D127B'))
        self.assertEqual(r.read_uint16(), 1)
        self.assertEqual(r.read_string(12), 'test')


if __name__ == '__main__':
    unittest.main()
