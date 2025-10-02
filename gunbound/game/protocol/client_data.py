from gunbound.game.client import ClientConnection
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader

"""
A inicialização da criptografia dos dados enviado pelo cliente é feita pela função sub_40B420 no GBS v440
"""
@BasePackageFactory.register(ClientPacket.CLI_CLIENT_DATA.value)
class ClientDataRecv(BasePackageRecv):

    def __init__(self, conn: ClientConnection, buf: BinaryReader):
        self.conn = conn
        self.inventory_repository: InventoryRepository = InventoryRepository()

    async def process(self):
        self.buf.read_uint8() # Desconhecido, sem sempre 1
        client_data = self.buf.read_bytes(100)
        client_data[9] = 0x24 # Sempre tem o 24, não sei o pq
        self

        await self.conn.on_send(ClientDataResp.success(self.conn))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_CLIENT_DATA.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class ClientDataResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, conn):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_CLIENT_DATA)
        buf.write_uint16(ServerCode.SRV_OK)

        return cls(buf)
    
    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}]")