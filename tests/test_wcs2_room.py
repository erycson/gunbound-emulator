"""WCS2 sala: 0x3106->0x3107 e 0x6050/0x6051/0x6052. Uso: python -m unittest tests.test_wcs2_room -v"""
import struct
import unittest
from gunbound.base.enums import RoomOptions, RoomMode
from gunbound.game.protocol.wcs2.room import (RoomChangeAllRecv, ReadyItemsGetRecv, ReadyItemsSetRecv,
                                              SRV_ROOM_CHANGE_ALL, SRV_READY_ITEMS)
from gunbound.util import BinaryReader
from tests.test_rooms_shop import FakeConn, manager


def change_all(stage, settings, capacity):
    return struct.pack('<HBBIB', 4, 1, stage, settings, capacity)


class RoomChangeAllTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.master, self.b = FakeConn('m6'), FakeConn('b6')
        self.room = await manager().create(self.master, RoomOptions('sala', RoomMode.SOLO, 4, ''))
        await self.room.join(self.b)

    async def test_ok(self):
        settings = self.room.options.settings | (int(self.room.options.mode) << 16)
        await RoomChangeAllRecv(self.master, BinaryReader(change_all(3, settings, 8))).process()
        self.assertEqual(self.master.last(SRV_ROOM_CHANGE_ALL)[2:4], b'\x00\x00')
        self.assertEqual((self.room.options.map, self.room.options.size), (3, 8))

    async def test_invalid_capacity_refused(self):
        settings = int(self.room.options.mode) << 16
        await RoomChangeAllRecv(self.master, BinaryReader(change_all(3, settings, 3))).process()
        self.assertEqual(self.master.last(SRV_ROOM_CHANGE_ALL)[2:4], b'\x01\x00')
        self.assertNotEqual(self.room.options.map, 3)

    async def test_not_master_ignored(self):
        await RoomChangeAllRecv(self.b, BinaryReader(change_all(3, 0, 8))).process()
        self.assertNotIn(SRV_ROOM_CHANGE_ALL, self.b.cmds())


class ReadyItemsTest(unittest.IsolatedAsyncioTestCase):
    async def test_roundtrip(self):
        a = FakeConn('items')
        a.room = await manager().create(a, RoomOptions('s', RoomMode.SOLO, 2, ''))
        await ReadyItemsGetRecv(a, BinaryReader(b'')).process()
        self.assertEqual(a.last(SRV_READY_ITEMS)[2:], b'\x00\x00\x00\x00')
        body = struct.pack('<H4I', 2, 10, 0xAAA7B, 0, 0) + b'lixo'
        await ReadyItemsSetRecv(a, BinaryReader(body)).process()
        await ReadyItemsGetRecv(a, BinaryReader(b'')).process()
        self.assertEqual(a.last(SRV_READY_ITEMS)[2:], b'\x00\x00' + body[:18])


if __name__ == '__main__':
    unittest.main()
