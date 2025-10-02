import datetime
from gunbound.game.client import ClientConnection
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.respository import InventoryRepository

"""
A inicialização da criptografia dos dados enviado pelo cliente é feita pela função sub_40B420 no GBS v440
"""
@BasePackageFactory.register(ClientPacket.CLI_CASH.value)
class CashRecv(BasePackageRecv):

    def __init__(self, conn: ClientConnection, buf: BinaryReader):
        self.conn = conn
        self.inventory_repository: InventoryRepository = InventoryRepository()

    async def process(self):
        cash = await self.inventory_repository.get_cash(self.conn.data['game']['Id'])
        self.conn.data['cash'] = cash

        await self.conn.on_send(CashResp.success(cash))

    def log_command(self, conn):
        cmd = ClientPacket.SRV_CASH.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class CashResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, cash):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_CASH)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint32(cash['Cash'])

        return cls(buf)
    
    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex()}")