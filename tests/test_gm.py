"""
Comandos de GM (0x5100 -> 0x5101), jogo solo do GM e teto de recompensa pelo multiplicador.
Uso: python -m unittest tests.test_gm -v
"""
import unittest
from gunbound.base.enums import RoomOptions, RoomMode, RoomStatus
from gunbound.game.protocol.enums import ServerPacket
from gunbound.game.protocol.game_play import reward_caps
from gunbound.game.protocol.gm_commands import GmCommands, SYNTAX_ERROR
from tests.test_rooms_shop import FakeConn, manager


class FakeClients:
    def __init__(self, *conns):
        self.clients = {c.id: c for c in conns}

    def size(self):
        return len(self.clients)


class FakeUsers:
    def __init__(self):
        self.banned = {}

    async def set_restrict_time(self, user_id, until):
        self.banned[user_id] = until
        return True


def conn(nick, authority=0):
    c = FakeConn(nick, authority)
    c.channel = None
    return c


class GmTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rooms = manager()
        self.gm, self.a = conn('gm', 100), conn('a')
        self.users = FakeUsers()
        self.cmd = GmCommands(self.gm, self.rooms, FakeClients(self.gm, self.a), self.users)

    async def test_unknown_and_syntax(self):
        self.assertEqual(await self.cmd.run('/nada'), SYNTAX_ERROR)
        self.assertEqual(await self.cmd.run('/ban x'), SYNTAX_ERROR)
        self.assertEqual(await self.cmd.run('/qsopt 9'), SYNTAX_ERROR)

    async def test_bcm_reaches_everyone(self):
        msg = await self.cmd.run('/bcm -a ola')
        self.assertIn('to 2', msg)
        self.assertEqual(self.a.last(ServerPacket.SRV_COMMAND)[2:], b'ola')

    async def test_ban_and_disconnect(self):
        msg = await self.cmd.run('/ban -d2 a cheat')
        self.assertIn('48 hours', msg)
        self.assertIn('a', self.users.banned)
        self.assertTrue(self.a.closing)

    async def test_mute(self):
        self.assertIn('120 seconds', await self.cmd.run('/mute a 120'))
        self.assertEqual(self.a.last(ServerPacket.SRV_CHAT_MUTE)[2:], (120).to_bytes(4, 'little'))
        self.assertEqual(await self.cmd.run('/mute a'), SYNTAX_ERROR)
        self.assertIn('5 seconds', await self.cmd.run('/silence a 5'))
        self.assertIsNone(await self.cmd.run('/gg'))  # S2 já mandou o 0x3430; o 0x5100 cru não tem resposta

    async def test_toid_and_qsopt(self):
        self.assertEqual(await self.cmd.run('/toid A'), 'ID: a NICKNAME: a')
        await self.cmd.run('/qsopt 4')
        self.assertEqual(self.rooms.quick_mode, RoomMode.JEWEL)

    async def test_motd_room(self):
        await self.cmd.run('/motd -r bem-vindo')
        self.assertEqual(self.rooms.motd(), 'bem-vindo')

    async def test_startgame_solo(self):
        room = await self.rooms.create(self.gm, RoomOptions('gm', RoomMode.SOLO, 2, None))
        self.gm.room = room
        self.assertIsNone(await self.cmd.run('/startgame'))
        self.assertEqual(room.status, RoomStatus.IN_GAME)
        self.assertNotIn(ServerPacket.SRV_START_GAME_ACK, self.gm.cmds())

    async def test_startgame_needs_room(self):
        self.assertIn('mestre', await self.cmd.run('/startgame'))


class RewardCapTest(unittest.TestCase):
    def test_caps_scale_with_factor(self):
        self.assertEqual(reward_caps({'gold_factor': 230, 'score_factor': 270}), (6900, 540))
        self.assertEqual(reward_caps({'gold_factor': 100, 'score_factor': 100}), (3000, 200))


if __name__ == '__main__':
    unittest.main()
