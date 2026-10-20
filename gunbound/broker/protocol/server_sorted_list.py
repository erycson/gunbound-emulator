from __future__ import annotations
import socket
import struct
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.broker.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
if TYPE_CHECKING:
    from gunbound.broker.managers import MonitorManager
    from gunbound.broker.gameserver import GameServer

@BasePackageFactory.register(ClientPacket.CLI_SORTED_SERVER_LIST.value)
@inject
class ServerSortedListRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn, buf: BinaryReader, server: 'MonitorManager' = Provide['monitor']):
        self.conn = conn
        self.buf = buf
        self.server = server

    async def process(self):
        order = self.buf.read_uint8()
        filterFlag = self.buf.read_uint8()
        startIndex = self.buf.read_uint16()

        await self.conn.on_send(ServerSortedListResp.success(self.server.all(), th=self.conn.th))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_SORTED_SERVER_LIST.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.broker.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

@BasePackageFactory.register(ClientPacket.CLI_SPECIFIC_SERVER_LIST.value)
@inject
class ServerSpecificListRecv(BasePackageRecv):
    """
    0x1101 (só o TH, aba dos servidores dos amigos, cliente 0x50a7b5): n x u16 índice, sem contagem (n = len/2).
    Resposta 0x1102 como o 0x1100, na ordem pedida, pulando índice desconhecido (broker original 0x408df2).
    O original recusa mais de 12 com RTC 7; o TH manda até 16, então aqui o limite é 16.
    """
    MAX_IDS = 16

    def __init__(self, conn, buf: BinaryReader, server: 'MonitorManager' = Provide['monitor']):
        self.conn = conn
        self.buf = buf
        self.server = server

    async def process(self):
        data = self.buf.read_bytes()
        if len(data) > self.MAX_IDS * 2:
            await self.conn.on_send(ServerSortedListResp.error(ServerCode.SRV_ERR_ERR_INVALID_SIZE))
            return
        servers = self.server.all()
        ids = [v[0] for v in struct.iter_unpack('<H', data[:len(data) // 2 * 2])]
        await self.conn.on_send(ServerSortedListResp.success([servers[i] for i in ids if i < len(servers)], th=self.conn.th))

    def log_command(self, conn):
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.broker.id:08X} SQ={seq:04X} CD={ClientPacket.CLI_SPECIFIC_SERVER_LIST.value:04X}] {self.buf.to_hex(4)}")


class ServerSortedListResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def error(cls, rtc: int):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_SERVER_LIST)
        buf.write_uint16(rtc)
        return cls(buf)

    @classmethod
    def success(cls, servers: list['GameServer'], th: bool = False):
        """th: o TH v404 (0x44c8c0) lê 13 bytes depois da descrição (ip, porta, 3 u16, online), sem grades/avatar."""
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
            if not th:
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