from __future__ import annotations
import socket
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.broker.protocol.enums import ClientPacket, ServerPacket
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
if TYPE_CHECKING:
    from gunbound.broker.managers import MonitorManager
    from gunbound.broker.gameserver import GameServer

@inject
@BasePackageFactory.register(ClientPacket.CLI_SORTED_SERVER_LIST.value)
class ServerSortedListRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn, buf: BinaryReader, server: 'MonitorManager' = Provide['Container.monitor']):
        self.conn = conn
        self.buf = buf
        self.server = server

    async def process(self):
        order = self.buf.read_uint8()
        filterFlag = self.buf.read_uint8()
        startIndex = self.buf.read_uint16()

        await self.conn.on_send(ServerSortedListResp.success(self.server.all()))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_SORTED_SERVER_LIST.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.broker.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class ServerSortedListResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, servers: list['GameServer']):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_SERVER_LIST)
        buf.write_uint8(0) # Desconhecido
        buf.write_uint8(0) # Desconhecido
        buf.write_uint8(1) # isLastPacket, 0 para dizer que ainda tem mais servidores
        buf.write_uint8(len(servers))

        for server in servers:
            buf.write_uint16(server.index)
            buf.write_int8(server.event)
            buf.write_uint8(len(server.name.encode('latin-1')))
            buf.write_string(server.name)
            buf.write_uint8(len(server.description.encode('latin-1')))
            buf.write_string(server.description)
            buf.write_bytes(socket.inet_aton(server.host))
            buf.write_uint16(server.port, le=False)
            buf.write_uint16(0) # Desconhecido
            buf.write_uint16(server.users_online)
            buf.write_uint16(server.users_max) # RecommendedMan
            buf.write_int8(server.grade_max)
            buf.write_int8(server.grade_min)
            buf.write_uint8(server.avatar_enabled)
            buf.write_uint8(server.is_online)

        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")