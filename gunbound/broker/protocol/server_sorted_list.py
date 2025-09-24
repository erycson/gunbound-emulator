import socket
from gunbound.broker.protocol.enums import ClientPacket, ServerPacket
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.broker.managers.gameserver import GameServerManager
from gunbound.broker.gameserver import GameServer
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader

@BasePackageFactory.register(ClientPacket.CLI_SORTED_SERVER_LIST.value)
class ServerSortedListRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn, buf: BinaryReader):
        self.conn = conn
        self.buf = buf

    async def process(self):
        order = self.buf.read_uint8()
        filterFlag = self.buf.read_uint8()
        startIndex = self.buf.read_uint16()
        servers = GameServerManager.get().all()

        await self.conn.on_send(ServerSortedListResp.success(servers))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_SORTED_SERVER_LIST.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.broker.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex()}")

class ServerSortedListResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    """
    00 00 Desconhecido
    01 -> isLastPacket
    01 ->  serverCount
        00 00 -> ServerId
        00 -> Event
        10 -> Name Len
        5B 53 31 5D 20 47 75 6E 62 6F 75 6E 64 20 57 43 -> Name
        16 -> Desc Len
        C1 72 65 61 20 6C 69 76 72 65 5C 6E 53 65 6D 20 61 76 61 74 61 72 -> Desc
        7F 00 00 01 -> IP
        20 A8 -> Port
        00 00 -> Desconhecido
        00 00 -> Desconhecido
        B8 0B -> Max Players
        13 -> Leve Min
        FC -> Level Max
        00 -> Is Online
        01 -> Avatar Enabled
    """
    @classmethod
    def success(cls, servers: list[GameServer]):
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
            buf.write_uint16(server.port)
            buf.write_bytes([0x00, 0x00, 0x00, 0x00]) # Desconhecido
            buf.write_uint16(server.users_max) # RecommendedMan
            buf.write_int8(server.grade_max)
            buf.write_int8(server.grade_min)
            buf.write_uint8(int(server.avatar_enabled))
            buf.write_uint8(int(server.is_online))

        return cls(buf)
    
    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex()}")