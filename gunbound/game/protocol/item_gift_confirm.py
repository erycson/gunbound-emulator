from __future__ import annotations
from typing import TYPE_CHECKING
from databases import Database
from dependency_injector.wiring import Provide, inject
from dependency_injector.providers import Configuration
from gunbound.base.managers import CryptoManager
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.base.enums import AcquisitionType, ExpireType, GiftMsgType, ReceiptGiftResult
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.repository import InventoryRepository
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_ITEM_GIFT_CONFIRM.value)
@inject
class ItemGiftConfirmRecv(BasePackageRecv):

    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        db: Database = Provide['database'],
        config: Configuration = Provide['config'],
        crypto: CryptoManager = Provide['crypto'],
        inventory_repository: 'InventoryRepository' = Provide['inventory_repository'],
    ):
        self.buf = buf
        self.conn = conn
        self.db = db
        self.config = config
        self.crypto = crypto
        self.inventory_repository = inventory_repository

    async def process(self):
        data = self.crypto.decrypt(self.buf.read_bytes(16))
        self.buf = BinaryReader(data)

        command = (self.buf.read_int32() - 0x8631607E) & 0xFFFFFFFF
        if command != ClientPacket.CLI_ITEM_GIFT_CONFIRM.value:
            print("Invalid command in ItemGiftConfirmRecv")
            return

        user_id = self.conn.data['profile']['Id']
        giftitem_id = self.buf.read_uint32()
        accepted = self.buf.read_uint8()

        giftmsg = await self.inventory_repository.get_giftmsg_from_giftitem(user_id, giftitem_id)
        if giftmsg is None:
            return
        
        giftitem = await self.inventory_repository.get_giftitem(user_id, giftitem_id)
        if giftitem is None:
            return

        acquisition = AcquisitionType.try_from(giftitem['Acquisition'])
        expire_type = ExpireType.try_from(giftmsg['ExpireType'])
        menu = await self.inventory_repository.get_menu(giftmsg['MenuId'], acquisition, expire_type)
        if menu is None:
            return
        
        if not accepted:
            price = menu.get(self.get_field_name(acquisition, expire_type))

            await self.inventory_repository.update_giftmsg_status(giftmsg['No'], giftitem['Sender'], user_id, GiftMsgType.Denied)
            if acquisition == AcquisitionType.Cash:
                await self.inventory_repository.insert_buy_info(self.config['product_version'], giftmsg['MenuId'], price, 0, acquisition)
                await self.inventory_repository.update_cash(user_id, price)
            elif acquisition == AcquisitionType.Gold:
                await self.inventory_repository.update_money(user_id, price)

            await self.inventory_repository.delete_giftitem(giftitem_id)
            await self.inventory_repository.update_receiptgift_result(giftitem_id, user_id, ReceiptGiftResult.Denied)
        else:
            chest = await self.insert_chest(user_id, menu, acquisition, expire_type)
            
            await self.inventory_repository.update_giftmsg_status(giftmsg['No'], giftitem['Sender'], user_id, GiftMsgType.Accepted)
            await self.inventory_repository.delete_giftitem(giftitem_id)
            await self.inventory_repository.update_receiptgift_result(giftitem_id, user_id, ReceiptGiftResult.Accepted)

            await self.conn.on_send(ItemGiftConfirmResp.success(chest, AcquisitionType.Gift, expire_type))

    async def insert_chest(self, user_id: str, menu: dict, acquisition: AcquisitionType, expire_type: str) -> list[dict]:
        chest: list[dict] = []

        period = self.calc_period(expire_type, menu['Period1'])
        chest_id = await self.inventory_repository.insert_chest(user_id, menu['Item1'], acquisition, expire_type, period, menu['Volume1'])
        chest.append({'chest_id': chest_id, 'item_no': menu['Item1'], 'period': period})

        if menu['Item2'] is not None:
            period = self.calc_period(expire_type, menu['Period2'])
            chest_id = await self.inventory_repository.insert_chest(user_id, menu['Item2'], acquisition, expire_type, period, menu['Volume2'])
            chest.append({'chest_id': chest_id, 'item_no': menu['Item2'], 'period': period})

        if menu['Item3'] is not None:
            period = self.calc_period(expire_type, menu['Period3'])
            chest_id = await self.inventory_repository.insert_chest(user_id, menu['Item3'], acquisition, expire_type, period, menu['Volume3'])
            chest.append({'chest_id': chest_id, 'item_no': menu['Item3'], 'period': period})

        if menu['Item4'] is not None:
            period = self.calc_period(expire_type, menu['Period4'])
            chest_id = await self.inventory_repository.insert_chest(user_id, menu['Item4'], acquisition, expire_type, period, menu['Volume4'])
            chest.append({'chest_id': chest_id, 'item_no': menu['Item4'], 'period': period})

        if menu['Item5'] is not None:
            period = self.calc_period(expire_type, menu['Period5'])
            chest_id = await self.inventory_repository.insert_chest(user_id, menu['Item5'], acquisition, expire_type, period, menu['Volume5'])
            chest.append({'chest_id': chest_id, 'item_no': menu['Item5'], 'period': period})

        return chest
    
    def get_field_name(self, acquisition: AcquisitionType, expire_type: str) -> str:
        if acquisition == AcquisitionType.Gold:
            return f"PriceByGoldFor{expire_type}"
        else: # Cash
            return f"PriceByCashFor{expire_type}"
    
    def log_command(self, conn):
        cmd = ClientPacket.CLI_ITEM_BUY.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class ItemGiftConfirmResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, chest: list[dict], acquisition: AcquisitionType, expire_type: ExpireType):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM_GIFT_CONFIRM)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint16(len(chest))

        for item in chest:
            buf.write_uint32(item['chest_id'])
            buf.write_uint32(item['item_no'])
            buf.write_uint8(0) # Desconhecido
            buf.write_char(acquisition.value)
            if expire_type == ExpireType.Infinite:
                buf.write_uint8(0)
                buf.write_uint32(0)
            else:
                buf.write_uint8(1)
                buf.write_uint32(item['period'])
            buf.write_uint8(1) # Desconhecido
            buf.write_uint8(1) # Desconhecido
            buf.write_uint32(0) # Desconhecido

        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex(8)}")