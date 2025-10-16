from __future__ import annotations
from typing import TYPE_CHECKING
from gunbound.base.managers import DatabaseManager
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.repository import InventoryRepository
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_ITEM_CONSUME.value)
class ItemConsumeRecv(BasePackageRecv):

    def __init__(self, conn: 'ClientConnection', buf: BinaryReader):
        self.buf = buf
        self.conn = conn
        self.inventory_repository: InventoryRepository = InventoryRepository()

    async def process(self):
        command = (self.buf.read_int32() - 0x8631607E) & 0xFFFFFFFF
        if command != ClientPacket.CLI_ITEM_CONSUME.value:
            return

        user_id = self.conn.data['profile']['Id']
        chest_id = self.buf.read_uint32()
        volume = self.buf.read_uint16() # Volume????
        if volume < 0:
            print(f"Volume inválido: {chest_id}")
            return

        chest_item = await self.inventory_repository.get_chest_item(user_id, chest_id)
        if volume > chest_item['Volume']:
            print(f"Volume solicitado maior que o disponível: {chest_id}")
            return
        elif chest_item['Volume'] <= 0:
            print(f"Item já consumido: {chest_id}")
            return

        refund = await self.inventory_repository.get_refund_value(chest_item['chest_id'], chest_item['Acquisition'])
        await self.inventory_repository.chest_consume(user_id, chest_id, volume)

        if refund is not None and chest_item['ExpireType'] == 'I':
            await self.inventory_repository.insert_receiptconsume(user_id, chest_item['Item'], volume, chest_item['Acquisition'], False, refund, chest_item['ExpireType'], chest_item['Expire'])
            await self.inventory_repository.update_money(user_id, refund)
        else:
            await self.inventory_repository.insert_receiptconsume(user_id, chest_item['Item'], volume, chest_item['Acquisition'], False, 0, chest_item['ExpireType'], chest_item['Expire'])

        await self.conn.on_send(ItemConsumeResp.success())

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ITEM_CONSUME.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class ItemConsumeResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM_CONSUME)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint16(0)

        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex(8)}")