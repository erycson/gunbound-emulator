from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.repository import UserRepository
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_CLIENT_DATA.value)
@inject
class ClientDataRecv(BasePackageRecv):
    """
    A inicialização da criptografia dos dados enviado pelo cliente é feita pela função sub_40B420 no GBS v440
    """

    def __init__(self, conn: 'ClientConnection', buf: BinaryReader, user_repository: 'UserRepository' = Provide['user_repository']):
        self.buf = buf 
        self.conn = conn
        self.user_repository = user_repository

    async def process(self):
        self.buf.read_uint8(0) # Desconhecido, sem sempre 0
        client_data = self.conn.data['game']['ClientData']
        client_data = bytearray([ord(char) if isinstance(char, str) else char for char in client_data])
        client_data[8] = 0 & 0xFF # AS vezes tem um 0x24 e outras não

        await self.conn.on_send(ClientDataResp.success(client_data))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_CLIENT_DATA.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class ClientDataResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, client_data: bytearray):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_CLIENT_DATA)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_bytes(client_data)
        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}]")