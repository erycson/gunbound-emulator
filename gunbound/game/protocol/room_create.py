from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.base.enums import RoomMap, RoomMode, RoomSize, RoomOptions
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.game.managers import RoomManager
    from gunbound.game.room import Room
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_ROOM_CREATE.value)
@inject
class RoomCreateRecv(BasePackageRecv):
    _strategy = None

    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        room_manager: 'RoomManager' = Provide['rooms'],
    ):
        self.conn = conn
        self.buf = buf
        self.manager = room_manager

    async def process(self):
        """
        @todo Verificar limites de usuários por canal.
        """
        if self.conn.channel is None:
            return
        if self.conn.room is not None:
            return

        len = self.buf.read_uint8()
        # Limita o tamanho do nome da sala, pois ao renomear, da pra colocar mais de 23 caracteres
        if len < 1 or len > 23:
            return

        name = self.buf.read_string(len)
        _ = self.buf.read_uint8() # Sempre 0xB2
        mode = RoomMap(self.buf.read_uint16())
        _ = self.buf.read_uint8() # Sempre 0x00
        password = self.buf.read_bytes(4)
        size = RoomSize(self.buf.read_uint8())

        # As vezes foi observado LIXO depois do primeiro byte, por isso essa proteção aqui
        password = None if password[0] == 0 else password.rstrip(b'\x00').decode('latin-1')    

        options = RoomOptions(name, RoomMap.RAMDOM, mode, size, password)
        room = await self.manager.create(self.conn, options)
        self.conn.room = room

        await self.conn.on_send(RoomCreateResp.success(room, self.manager.config['announcement']))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ROOM_CREATE.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class RoomCreateResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, room: Room, announcement: str) -> 'RoomCreateResp':
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ROOM_CREATE)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint16(room.id)
        buf.write_uint8(0) # ???
        buf.write_string(announcement)
        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)
        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex(8)}")