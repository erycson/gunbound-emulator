import datetime
from gunbound.game.client import ClientConnection
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.respository import InventoryRepository

"""
A inicialização da criptografia dos dados enviado pelo cliente é feita pela função sub_40B420 no GBS v440
"""
@BasePackageFactory.register(ClientPacket.CLI_ITEM.value)
class ItemRecv(BasePackageRecv):

    def __init__(self, conn: ClientConnection, buf: BinaryReader):
        self.conn = conn
        self.inventory_repository: InventoryRepository = InventoryRepository()

    async def process(self):
        chest = await self.inventory_repository.get_chest(self.conn.data['game']['Id'])
        await self.conn.on_send(ItemResp.success(chest))

    def log_command(self, conn):
        cmd = ClientPacket.SRV_ITEM.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class ItemResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, chest):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint16(len(chest))

        for item in reversed(chest):
            buf.write_uint32(item['No'])
            buf.write_uint32(item['Item'])
            buf.write_uint8(item['Wearing'])
            buf.write_char(item['Acquisition'])

            if item['ExpireType'] == 'I': # I = Infinito
                buf.write_uint8(0)
                buf.write_uint8(True) # Sempre ativo
            else:
                # W = Week, M = Month
                remaining_seconds = datetime.strptime(item['Expire'], "%Y-%m-%d %H:%M:%S").timestamp() - datetime.now().timestamp()
                is_active = remaining_seconds > 0

                buf.write_uint8(1)
                buf.write_uint32(int(remaining_seconds)) # Ignora os milisegundos
                buf.write_uint8(is_active)

            buf.write_uint32(item['Volume'])
            buf.write_uint8(1)  # Desconhecido
            buf.write_uint32(item['PlaceOrder'])
            buf.write_uint8(item['Recovered'])

        return cls(buf)
    
    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)

        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex()}")