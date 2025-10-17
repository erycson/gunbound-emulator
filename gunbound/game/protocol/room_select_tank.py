from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.base.enums import Tank
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.repository import UserRepository
    from gunbound.game.client import ClientConnection

@inject
@BasePackageFactory.register(ClientPacket.CLI_ROOM_SELECT_TANK.value)
class RoomSelectTankRecv(BasePackageRecv):
    _strategy = None

    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        user_repository: 'UserRepository' = Provide['Container.user_repository'],
    ):
        self.conn = conn
        self.buf = buf
        self.user_repository = user_repository

    async def process(self):
        """
        @todo Verificar limites de usuários por canal.
        """
        tank_id = self.buf.read_uint16()
        if not tank_id in Tank._value2member_map_:
            return
        
        client_data = self.conn.data['game']['ClientData']
        client_data = tank_id.to_bytes(2, 'little') + client_data[2:]
        self.conn.data['game']['ClientData'] = client_data
        
        await self.conn.on_send(RoomSelectTankResp.success())

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ROOM_SELECT_TANK.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class RoomSelectTankResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ROOM_SELECT_TANK)
        buf.write_uint16(ServerCode.SRV_UPDATED)
        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)
        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}]")