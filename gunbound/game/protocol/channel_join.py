from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol import ClientPacket, ServerPacket, ServerCode
from gunbound.game import phase
if TYPE_CHECKING:
    from gunbound.game.channel import Channel
    from gunbound.game.managers import ChannelManager
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_CHANNEL_JOIN.value)
@inject
class ChannelJoinRecv(BasePackageRecv):
    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        channel_manager: 'ChannelManager' = Provide['channels'],
    ):
        self.conn = conn
        self.buf = buf
        self.channel_manager = channel_manager

    async def process(self):
        """
        @todo Verificar limites de usuários por canal.
        """
        channel_id = self.buf.read_int16() # -1, 0, 1, ... 7,, -1 = Aleatorio
        if channel_id < -1 or channel_id > 7:
            return

        # Trocar de canal (inclusive -1) é como o cliente WC sai da sala (Protocolo-Salas.md 5.10)
        if self.conn.room is not None:
            await self.conn.room.room_manager.leave(self.conn)

        old_channel = self.conn.channel

        new_channel = self.channel_manager.get(channel_id) if channel_id != -1 else self.channel_manager.get_least_populated()
        channel_changed = await new_channel.add(self.conn)
        if channel_changed:
            # Envia o cliente para o novo canal
            self.conn.channel = new_channel
            await self.conn.on_send(await ChannelJoinResp.success(new_channel, self.conn))

            # Avisar o canal novo que o usuário entrou
            position = new_channel.get_client_position(self.conn)
            await new_channel.broadcast(ChannelJoinResp.success_update(self.conn, position), excepts = [self.conn.id])
        else:
            await self.conn.on_send(ChannelJoinResp.channel_full(self.conn))

        # Avisar o canal antigo que o usuário saiu
        if old_channel is not None and channel_changed:
            position = old_channel.get_client_position(self.conn)
            await old_channel.remove(self.conn)
            await old_channel.broadcast(ChannelJoinResp.success_remove(position))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_CHANNEL_JOIN.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class ChannelJoinResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf

    @classmethod
    async def success(cls, channel: Channel, conn: ClientConnection):
        clients = await channel.get_all()

        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_CHANNEL_JOIN)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint16(channel.id)
        buf.write_uint8(channel.get_highest_channel_position())
        buf.write_uint8(len(clients))

        for position, conn in clients:
            buf.write_uint8(position)
            buf.write_string(conn.data['profile']['Nickname'], 12)
            buf.write_uint8(1)  # ???
            buf.write_string(conn.data['game']['Guild'], 8)
            buf.write_bytes(phase.of(conn).grades(conn.data['game']))
        
        buf.write_string(conn.server.config['announcement'])
        return cls(buf)
    
    @classmethod
    def success_update(cls, conn: ClientConnection, position: int):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_CHANNEL_JOIN_UPDATE)
        buf.write_uint8(position)
        buf.write_string(conn.data['profile']['Nickname'], 12)
        buf.write_uint8(1)  # ???
        buf.write_string(conn.data['game']['Guild'], 8)
        buf.write_bytes(phase.of(conn).grades(conn.data['game']))
        return cls(buf)

    @classmethod
    def success_remove(cls, position: int):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_CHANNEL_JOIN_REMOVE)
        buf.write_uint8(position)
        return cls(buf)

    @classmethod
    def channel_full(cls, conn: ClientConnection):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_CHANNEL_JOIN)
        buf.write_uint16(ServerCode.SRV_CHANNEL_FULL)
        return cls(buf)

    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)

        if self.buf.size() == 8:
            rtc = reader.read_uint16(pos=6)
            print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} {rtc:04X}]")
        else:
            print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")