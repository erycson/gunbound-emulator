from __future__ import annotations
from typing import TYPE_CHECKING
from gunbound.game.channel import Channel
from gunbound.game.managers import ChannelManager
from gunbound.game.protocol import ClientPacket, ServerPacket, ServerCode
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection


@BasePackageFactory.register(ClientPacket.CLI_CHANNEL_JOIN.value)
class ChannelJoinRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn: 'ClientConnection', buf: BinaryReader):
        self.conn = conn
        self.buf = buf
        self.manager: ChannelManager = ChannelManager.get_instance()

    async def process(self):
        """
        @todo Verificar limites de usuários por canal.
        """
        channel_id = self.buf.read_int16() # -1, 0, 1, ... 7,, -1 = Aleatorio
        if channel_id < -1 or channel_id > 7:
            return

        channel = self.manager.get(channel_id) if channel_id != -1 else self.manager.get_least_populated()
        if await channel.add(self.conn):
            await self.conn.on_send(ChannelJoinResp.success(self.conn, channel))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_CHANNEL_JOIN.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class ChannelJoinResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, conn: ClientConnection, channel: Channel):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_CHANNEL_JOIN)
        buf.write_uint16(ServerCode.SRV_OK) # ???
        buf.write_uint16(0)
        buf.write_uint16(channel.id)
        buf.write_string(conn.data['profile']['Nickname'], 12)
        buf.write_uint8(1) # ???
        buf.write_string(conn.data['game']['Guild'], 8)
        buf.write_int16(conn.data['game']['TotalGrade'])
        buf.write_int16(conn.data['game']['SeasonGrade'])
        buf.write_int16(conn.data['game']['CountryGrade'])
        buf.write_uint16(conn.data['game']['Country'])
        buf.write_string(conn.server.config['announcement'])
        
        return cls(buf)
    
    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")