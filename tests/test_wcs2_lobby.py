"""WCS2 canal 0x7010, megafone 0x6054/0x5010 e convite 0x3450/0x3452. Uso: python -m unittest tests.test_wcs2_lobby -v"""
import struct
import unittest
from unittest import mock
from gunbound.base.enums import RoomOptions, RoomMode
from gunbound.game.channel import Channel
from gunbound.game.protocol.wcs2 import lobby
from gunbound.util import BinaryReader
from tests.test_rooms_shop import FakeConn, manager


class Clients:
    def __init__(self, *conns):
        self.clients = {c.id: c for c in conns}


class Inv:
    def __init__(self, item, volume):
        self.row = {'Item': item, 'Volume': volume}
        self.used = 0

    async def get_chest_item(self, uid, no):
        return self.row if no == 77 else None

    async def chest_consume(self, uid, no, v):
        self.used += v


def use(serial, kind=2):
    return struct.pack('<BHIIHI', kind, 0, serial, 0, 0, 0)


class LobbyTest(unittest.IsolatedAsyncioTestCase):
    async def test_7010(self):
        a = FakeConn('a')
        await lobby.ChannelInfoRecv(a, BinaryReader(b'')).handle()
        self.assertEqual(a.sent[-1], b'\x11\x70\x00\x00\x00\x00')

    async def test_megaphone(self):
        a, b = FakeConn('a'), FakeConn('b')
        inv = Inv(lobby.MEGAPHONE_ITEM, 3)
        await lobby.ItemUseRecv(a, BinaryReader(use(77))).handle(inventory_repository=inv)
        self.assertEqual(a.last(0x6055)[2:], struct.pack('<HIII', 0, 77, 2, lobby.MEGAPHONE_ITEM))
        body = bytes([8, 1, 9]) + b'x] ola :)'
        with mock.patch.object(lobby, 'decrypt_blocks', lambda conn, data, cmd: BinaryReader(data)), \
                mock.patch.object(lobby, 'logged_in', lambda clients: list(clients.clients.values())):
            await lobby.BcmV584Recv(a, BinaryReader(body)).handle(clients=Clients(a, b))
            await lobby.BcmV584Recv(a, BinaryReader(body)).handle(clients=Clients(a, b))  # sem novo item: nada
        msg = b'a] ola :)'
        self.assertEqual(b.sent, [struct.pack('<H', 0x5011) + bytes([8, 1, len(msg)]) + msg])
        self.assertEqual(inv.used, 1)

    async def test_megaphone_refused(self):
        a = FakeConn('a')
        await lobby.ItemUseRecv(a, BinaryReader(use(5))).handle(inventory_repository=Inv(lobby.MEGAPHONE_ITEM, 1))
        self.assertEqual(a.last(0x6055)[2:4], struct.pack('<H', lobby.ITEM_USE_ERROR))

    async def test_invite(self):
        master, guest, other = FakeConn('m'), FakeConn('guest'), FakeConn('o')
        channel = Channel(None, 0)
        for c in (master, guest, other):
            await channel.add(c)
        master.channel = channel
        room = await manager().create(master, RoomOptions('sala', RoomMode.SOLO, 2, None))
        other.room = room
        await lobby.InviteListRecv(master, BinaryReader(b'')).handle()
        body = master.last(0x3451)
        self.assertEqual(struct.unpack_from('<H', body, 2)[0], 1)
        self.assertEqual(body[9:14], b'guest')
        req = struct.pack('<H', room.id) + b'1234' + b'vem'.ljust(20, b'\x00') + b'GUEST'.ljust(12, b'\x00')
        await lobby.InviteSendRecv(master, BinaryReader(req)).handle()
        self.assertEqual(guest.last(0x2025)[2:], req[:26] + b'm'.ljust(12, b'\x00'))


if __name__ == '__main__':
    unittest.main()
