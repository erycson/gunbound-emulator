from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.repository import InventoryRepository
    from gunbound.game.client import ClientConnection

@inject
@BasePackageFactory.register(ClientPacket.CLI_ITEM.value)
class ItemRecv(BasePackageRecv):
    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        inventory_repository: 'InventoryRepository' = Provide['Container.inventory_repository'],
    ):
        self.buf = buf
        self.conn = conn
        self.inventory_repository = inventory_repository

    async def process(self):
        chest = await self.inventory_repository.get_chest(self.conn.data['profile']['Id'])
        await self.conn.on_send(ItemResp.success(chest))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ITEM.value
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

            if item['Expire'] is None:
                buf.write_uint8(0)
                buf.write_uint8(True) # Sempre ativo
            else:
                buf.write_uint8(1)
                buf.write_uint32(int(item['Expire']))
                buf.write_uint8(item['Expire'] > 0)

            buf.write_uint32(item['Volume'])
            buf.write_uint8(1)  # Desconhecido
            buf.write_uint32(item['PlaceOrder'])
            buf.write_uint8(item['Recovered'])

        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")