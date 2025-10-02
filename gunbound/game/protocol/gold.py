from gunbound.game.client import ClientConnection
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.respository import InventoryRepository

@BasePackageFactory.register(ClientPacket.CLI_GOLD.value)
class GoldRecv(BasePackageRecv):

    def __init__(self, conn: ClientConnection, buf: BinaryReader):
        self.conn = conn
        self.inventory_repository: InventoryRepository = InventoryRepository()

    async def process(self):
        money = await self.inventory_repository.get_money(self.conn.data['game']['Id'])
        await self.conn.on_send(GoldResp.success(money))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_GOLD.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class GoldResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, money):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_GOLD)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint32(money['Money'])

        return cls(buf)
    
    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex()}")