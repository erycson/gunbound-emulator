from __future__ import annotations
from typing import TYPE_CHECKING
from gunbound.game.protocol import ClientPacket, ServerPacket
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_GET_SESSION_ID.value)
class GetSessionIdRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn: 'ClientConnection', buf: BinaryReader):
        self.conn = conn
        self.buf = buf

    async def process(self):
        await self.conn.on_send(GetSessionIdResp.success(self.conn.client_manager.rand.next()))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_GET_SESSION_ID.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class GetSessionIdResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    """
    04 D1 00 00 -> SessionId 1233
    """
    @classmethod
    def success(cls, session_id: int):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_SESSION_ID)
        buf.write_uint32(session_id)
        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")