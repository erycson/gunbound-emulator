"""Quick start 0x2130: entra em sala livre (0x2133), cria QuickStartRoom (0x2132) ou falha (0x2131 RTC 8)."""
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

    async def test_joins_free_room(self):
        rooms, a, b = manager(), FakeConn('a'), FakeConn('b')
        await rooms.create(a, RoomOptions('sala', RoomMode.SOLO, 8, None))
        await self.quick(b, rooms)
        self.assertIn(ServerPacket.SRV_ROOM_QUICK_START, b.cmds())
        self.assertIs(b.room, a.room)

    async def test_create_fails(self):
        rooms, a = manager(), FakeConn('a')
        with mock.patch.object(rooms, 'create', mock.AsyncMock(return_value=None)):
            await self.quick(a, rooms)
        body = a.last(ServerPacket.SRV_ROOM_QUICK_FAIL)
        self.assertEqual(struct.unpack_from('<H', body, 2)[0], 8)


if __name__ == '__main__':
    unittest.main()
