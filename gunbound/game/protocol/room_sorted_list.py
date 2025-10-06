from __future__ import annotations
from typing import TYPE_CHECKING
from gunbound.game.protocol import ClientPacket, ServerPacket, RoomSortList
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
if TYPE_CHECKING:
    from gunbound.game.room import Room
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_ROOM_SORTED_LIST.value)
class RoomSelectTankRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn: 'ClientConnection', buf: BinaryReader):
        from gunbound.game.managers import RoomManager

        self.conn = conn
        self.buf = buf
        self.manager: 'RoomManager' = RoomManager.get_instance()

    async def process(self):
        """
        @todo Verificar limites de usuários por canal.
        """
        if self.conn.channel is None:
            return

        sort_by = self.buf.read_uint8()
        if sort_by not in RoomSortList._value2member_map_:
            return
        current_page = self.buf.read_uint16()
        per_page = self.buf.read_uint16()

        rooms = await self.manager.get_rooms(sort_by, current_page, per_page)
        await self.conn.on_send(RoomSelectTankResp.success(rooms))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ROOM_SORTED_LIST.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class RoomSelectTankResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, rooms: list[Room]):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ROOM_SORTED_LIST)
        buf.write_uint16(len(rooms))

        for room in rooms:
            buf.write_uint16(room.id) # ID começa em 0 no servidor, mas no cliente começa em 1
            buf.write_uint8(len(room.name))
            buf.write_string(room.options.name)
            buf.write_uint16(room.options.map.value)
            buf.write_uint16(room.options.mode.value)
            buf.write_uint16(room.status.value)
            buf.write_uint16(room.player_count())
            buf.write_uint16(room.options.size.value)
            buf.write_uint8(room.options.is_protected())

        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)
        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}]")