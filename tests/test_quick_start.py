"""Quick start 0x2130: entra numa QuickStartRoom (0x2133), cria uma (0x2132) ou falha (0x2131 RTC 8)."""
import struct
import unittest
from unittest import mock
from tests.test_rooms_shop import FakeConn, manager
from gunbound.base.enums import RoomOptions, RoomMode
from gunbound.game.protocol.enums import ServerPacket
from gunbound.util import BinaryReader


class QuickStartTest(unittest.IsolatedAsyncioTestCase):
    async def quick(self, conn, rooms):
        from gunbound.game.protocol.room_join import RoomQuickStartRecv
        await RoomQuickStartRecv(conn, BinaryReader(b'')).handle(rooms=rooms)

    async def test_creates_room(self):
        rooms, a = manager(), FakeConn('a')
        await self.quick(a, rooms)
        body = a.last(ServerPacket.SRV_ROOM_QUICK_CREATE)
        self.assertEqual(struct.unpack_from('<H', body, 2)[0], 0)  # rtc
        self.assertEqual(body[4], 0)                               # slot do dono
        self.assertIn(b'QuickStartRoom', body)
        self.assertIs(a.room, rooms.get(struct.unpack_from('<H', body, 5)[0]))
        # QuickStartOption 0x451C2 (Score) e QuickStartMan 6; fora das listas (+0xbd)
        self.assertEqual((a.room.options.settings, a.room.options.size, a.room.auto), (0x451C2, 6, True))

    async def test_joins_only_quick_rooms(self):
        rooms, a, b, c = manager(), FakeConn('a'), FakeConn('b'), FakeConn('c')
        await rooms.create(a, RoomOptions('sala', RoomMode.SOLO, 8, None))
        await self.quick(b, rooms)                      # sala comum não serve: cria a QuickStartRoom
        self.assertIsNot(b.room, a.room)
        await self.quick(c, rooms)
        self.assertIn(ServerPacket.SRV_ROOM_QUICK_START, c.cmds())
        self.assertIs(c.room, b.room)

    async def test_qsopt_and_man(self):
        rooms, a = manager(), FakeConn('a')
        rooms.quick_mode, rooms.quick_min_players = RoomMode.JEWEL, 4
        await self.quick(a, rooms)
        self.assertEqual((a.room.options.settings & 0xC0000, a.room.options.size), (0xC0000, 4))
        rooms.quick_min_players = 0                     # o Setting.txt do pacote "Season 2 server": QuickStart sempre falha
        b = FakeConn('b')
        await self.quick(b, rooms)
        self.assertEqual(struct.unpack_from('<H', b.last(ServerPacket.SRV_ROOM_QUICK_FAIL), 2)[0], 8)

    async def test_create_fails(self):
        rooms, a = manager(), FakeConn('a')
        with mock.patch.object(rooms, 'create', mock.AsyncMock(return_value=None)):
            await self.quick(a, rooms)
        body = a.last(ServerPacket.SRV_ROOM_QUICK_FAIL)
        self.assertEqual(struct.unpack_from('<H', body, 2)[0], 8)


if __name__ == '__main__':
    unittest.main()
