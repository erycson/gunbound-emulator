from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import AcquisitionType, ExpireType
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util import BinaryWriter, BinaryReader, dump
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.repository import InventoryRepository
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_ITEM_CONSUME.value)
@inject
class ItemConsumeRecv(BasePackageRecv):

    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        inventory_repository: 'InventoryRepository' = Provide['inventory_repository']
    ):
        self.buf = buf
        self.conn = conn
        self.inventory_repository = inventory_repository

    async def process(self):
        """
        @todo Eu não sei em que momento itens de baú são removidos quando Volume == 0
        """

        data = self.conn.decrypt(self.buf.read_bytes())
        dump(data)
        buf = BinaryReader(data)

        command = (buf.read_int32() - 0x8631607E) & 0xFFFFFFFF
        if command != ClientPacket.CLI_ITEM_CONSUME.value:
            return

        user_id = self.conn.data['profile']['Id']
        chest_id = buf.read_uint32()
        volume = buf.read_uint16() # Volume????
        if volume < 0:
            print(f"Volume inválido: {chest_id} -> volume: {volume}")
            return
        
        chest_item = await self.inventory_repository.get_chest_item(user_id, chest_id)
        if volume > chest_item['Volume']:
            print(f"Volume solicitado maior que o disponível: {volume} de {chest_item['Volume']}")
            return
        elif chest_item['Volume'] <= 0:
            print(f"Item já consumido: {chest_id}")
            return

        expire_type = ExpireType.try_parse(chest_item['ExpireType'])
        acquisition = AcquisitionType.try_parse(chest_item['Acquisition'])
        refund = await self.inventory_repository.get_refund_value(chest_item['Item'], acquisition)
        await self.inventory_repository.chest_consume(user_id, chest_id, volume)

        if refund is not None and expire_type == ExpireType.Infinite:
            await self.inventory_repository.insert_receiptconsume(user_id, chest_item['Item'], volume, False, refund, expire_type, chest_item['Expire'])
            await self.inventory_repository.update_money(user_id, refund)
        else:
            await self.inventory_repository.insert_receiptconsume(user_id, chest_item['Item'], volume, False, 0, expire_type, chest_item['Expire'])

        await self.conn.on_send(ItemConsumeResp.success())

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ITEM_CONSUME.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

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