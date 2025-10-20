from __future__ import annotations
from typing import TYPE_CHECKING
from databases import Database
from dependency_injector.wiring import Provide, inject
from dependency_injector.providers import Configuration
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.base.enums import ReceiptGiftResult, AcquisitionType, ReceiptBuyType, MessageType, ExpireType
from gunbound.util import BinaryReader, BinaryWriter
from gunbound.game.protocol import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.base.managers import CryptoManager
    from gunbound.repository import UserRepository, InventoryRepository
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_ITEM_GIFT_BUY.value)
@inject
class ItemGiftBuyRecv(BasePackageRecv):

    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        db: Database = Provide['database'],
        config: Configuration = Provide['config'],
        crypto_manager: 'CryptoManager' = Provide['crypto'],
        user_repository: 'UserRepository' = Provide['user_repository'],
        inventory_repository: 'InventoryRepository' = Provide['inventory_repository'],
    ):
        self.buf = buf
        self.conn = conn
        self.db: Database = db
        self.config = config
        self.crypto_manager = crypto_manager
        self.user_repository = user_repository
        self.inventory_repository = inventory_repository

    async def process(self):
        data = self.crypto_manager.decrypt(self.buf.read_bytes())
        data = data[:4] + b''.join([data[i+4:i+16] for i in range(0, len(data), 16)])
        self.buf = BinaryReader(data)

        command = (self.buf.read_int32() - 0x8631607E) & 0xFFFFFFFF
        if command != ClientPacket.CLI_ITEM_GIFT_BUY.value:
            return

        sender_id = self.conn.data['profile']['Id']
        menu_no = self.buf.read_uint32()
        gender = self.buf.read_uint8() # 0 = Comprando pra outro, 1 = Comprando pra si mesmo
        expire_type = ExpireType.try_parse_int(self.buf.read_uint8())
        acquisition = AcquisitionType.try_parse_int(self.buf.read_uint8())
        receiver_id = self.buf.read_string(16) # Receiver ID
        receiver_nickname = self.buf.read_string(12) # Nickname ???, não sei pq, mas é enviado
        message_length = self.buf.read_uint8()
        message = self.buf.read_string(message_length) if message_length > 0 else None

        if acquisition is None or expire_type is None:
            return

        # Verifica quanto o usuário tem do ativo necessário (cash ou gold)
        asset = 0
        if acquisition == AcquisitionType.Cash:
            asset = await self.inventory_repository.get_cash(sender_id)
        elif acquisition == AcquisitionType.Gold:
            asset = await self.inventory_repository.get_money(sender_id)

        receiver_gender = await self.user_repository.get_gender(receiver_id)
        if receiver_gender != gender:
            await self.conn.on_send(ItemGiftBuyResp.wrong_gender())
            return
        
        menu = await self.inventory_repository.get_menu(menu_no, acquisition, expire_type)
        
        price = menu.get(self.get_field_name(acquisition, expire_type))
        if price is None or asset < price:
            return

        transaction = await self.db.transaction()
        try:
            # Insere o presente
            giftitem_id = await self.inventory_repository.insert_giftitem(sender_id, receiver_id, menu_no, acquisition)
            await self.inventory_repository.insert_giftmsg(sender_id, receiver_id, menu_no, giftitem_id, MessageType.Gift, message, expire_type)

            # Insere o recibo do presente
            receiptgift_id = await self.inventory_repository.insert_receiptgift(sender_id, receiver_id, menu_no, receiver_nickname, ReceiptGiftResult.Requested, expire_type)   # Não sei pra quer serve R
            await self.inventory_repository.update_giftitem_receiptgift_id(giftitem_id, receiptgift_id)

            # Insere o recibo da compra
            receiptbuy_id = await self.inventory_repository.insert_receiptbuy(sender_id, menu_no, acquisition, price, ReceiptBuyType.Gift, expire_type)
            await self.inventory_repository.update_receiptbuy_receiptgift_id(receiptbuy_id, receiptgift_id)

            # Desconta o ativo (cash ou gold)
            if acquisition == AcquisitionType.Cash:
                if not await self.inventory_repository.update_cash(sender_id, -price):
                    await transaction.rollback()
                    return
            elif acquisition == AcquisitionType.Gold:
                if not await self.inventory_repository.update_money(sender_id, -price):
                    await transaction.rollback()
                    return
            
            if (acquisition == AcquisitionType.Cash):
                await self.inventory_repository.insert_buy_info(self.config.product_version(), menu_no, price, asset, acquisition)
            
            await transaction.commit()
            
            await self.conn.on_send(ItemGiftBuyResp.success())
        except:
            await transaction.rollback()

    def get_field_name(self, acquisition: AcquisitionType, expire_type: str) -> str:
        if acquisition == AcquisitionType.Gold:
            return f"PriceByGoldFor{expire_type}"
        else: # C
            return f"PriceByCashFor{expire_type}"

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ITEM_GIFT_BUY.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class ItemGiftBuyResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM_GIFT_BUY)
        buf.write_uint16(ServerCode.SRV_OK)
        return cls(buf)
    
    @classmethod
    def wrong_gender(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM_GIFT_BUY)
        buf.write_uint16(ServerCode.SRV_WRONG_GENDER)
        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex(8)}")