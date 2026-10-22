"""
Comandos de GM (0x5100 -> 0x5101), jogo solo do GM e teto de recompensa pelo multiplicador.
Uso: python -m unittest tests.test_gm -v
"""
import unittest
from gunbound.base.enums import RoomOptions, RoomMode, RoomStatus
from gunbound.game.protocol.enums import ServerPacket
from gunbound.game.protocol.game_play import anu_verdict
from gunbound.game.protocol.gm_commands import GmCommands, SYNTAX_ERROR, start_echo
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

    def test_start_echo_modes(self):  # cliente 0x433770: seed + 6x3 no Jewel (modo 3), 3x3 no modo 4
        self.assertEqual(len(start_echo(0)), 4)
        jewel = start_echo(0xC0000)
        self.assertEqual(len(jewel), 4 + 18)
        self.assertTrue(all(b < 3 for b in jewel[6::3]))
        mode4 = start_echo(0x100000)
        self.assertEqual(len(mode4), 4 + 9)
        self.assertTrue(all(b in (1, 2, 4, 8, 16) for b in mode4[6::3]))

    async def test_mobile(self):
        """/mobile nome [slot|all]: o próprio, o de um slot ou o de todos; os ocultos também (Dragon)."""
        self.assertIn('sala aguardando', await self.cmd.run('/mobile ice'))
        room = await self.rooms.create(self.gm, RoomOptions('gm', RoomMode.SOLO, 4, None))
        self.gm.room = room
        await room.join(self.a)
        a = room.player(self.a)
        self.assertIn('Dragon', await self.cmd.run('/mobile dragon'))
        self.assertEqual((room.player(self.gm).tank1, a.tank1), (0x11, 0x00))
        await self.cmd.run(f'/mobile ice {a.slot}')
        self.assertEqual((room.player(self.gm).tank1, a.tank1), (0x11, 0x0A))
        await self.cmd.run('/mobile j.d all')
        self.assertEqual({p.tank1 for p in room.players.values()}, {0x08})
        self.assertIn('não existe', await self.cmd.run('/mobile nada'))
        self.assertIn('Ninguém', await self.cmd.run('/mobile ice 7'))

    async def test_startgame_needs_room(self):
        self.assertIn('mestre', await self.cmd.run('/startgame'))


class AnuTest(unittest.TestCase):
    def test_original_limits(self):  # padrões do original: log > 3000/30, derruba > 6000/50 ou < -2500/-100
        cases = [(100, 5), (3001, 0), (0, 31), (6001, 0), (0, 51), (-2501, 0), (0, -101), (-100, -10)]
        self.assertEqual([anu_verdict(g, s, {}) for g, s in cases], ['ok', 'log', 'log', 'drop', 'drop', 'drop', 'drop', 'ok'])
        self.assertEqual(anu_verdict(4000, 0, {'anu': {'drop_gold': 3500}}), 'drop')


if __name__ == '__main__':
    unittest.main()
