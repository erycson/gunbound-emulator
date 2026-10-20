from __future__ import annotations
from typing import TYPE_CHECKING
from gunbound.base.database import Database
from dependency_injector.wiring import Provide, inject
from dependency_injector.providers import Configuration
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.base.enums import AcquisitionType, ExpireType, GiftMsgType, ReceiptGiftResult
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.game.protocol.item_buy import ItemBuyRecv
if TYPE_CHECKING:
    from gunbound.base.managers import CryptoManager
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
        crypto_manager: 'CryptoManager' = Provide['crypto'],
        inventory_repository: 'InventoryRepository' = Provide['inventory_repository'],
    ):
        self.buf = buf
        self.conn = conn
        self.db = db
        self.config = config
        self.crypto_manager = crypto_manager
        self.inventory_repository = inventory_repository

    async def process(self):
        data = self.crypto_manager.decrypt(self.buf.read_bytes(16))
        self.buf = BinaryReader(data)

        command = (self.buf.read_int32() - 0x8631607E) & 0xFFFFFFFF
        if command != ClientPacket.CLI_ITEM_GIFT_CONFIRM.value:
            print("Invalid command in ItemGiftConfirmRecv")
            return

        user_id = self.conn.data['profile']['Id']
        giftitem_id = self.buf.read_uint32()
        accepted = self.buf.read_uint8()

        # o original (0x42e519) responde 0x6009 a todo 0x6008: só o RTC 0 avança o diálogo do cliente (v440 0x4f3d01)
        giftmsg = await self.inventory_repository.get_giftmsg_from_giftitem(user_id, giftitem_id)
        giftitem = giftmsg and await self.inventory_repository.get_giftitem(user_id, giftitem_id)
        if giftitem is None:
            print(f"[{self.conn.addr}] 0x6008: presente {giftitem_id} não encontrado")
            return await self.conn.on_send(ItemGiftConfirmResp.error())

        acquisition = AcquisitionType.try_parse(giftitem['Acquisition'])
        expire_type = ExpireType.try_parse(giftmsg['ExpireType'])
        menu = await self.inventory_repository.get_menu(giftmsg['MenuId'], acquisition, expire_type)
        if menu is None:
            print(f"[{self.conn.addr}] 0x6008: menu {giftmsg['MenuId']} não encontrado")
            return await self.conn.on_send(ItemGiftConfirmResp.error())
        
        if not accepted:
            price = menu.get(self.get_field_name(acquisition, expire_type))

            await self.inventory_repository.update_giftmsg_status(giftmsg['No'], user_id, giftitem['Sender'], GiftMsgType.Denied)
            if acquisition == AcquisitionType.Cash:
                await self.inventory_repository.insert_buy_info(self.config['product_version'], giftmsg['MenuId'], price, 0, acquisition)
                await self.inventory_repository.update_cash(giftitem['Sender'], price)  # o original devolve ao remetente (GiftItem.Sender)
            elif acquisition == AcquisitionType.Gold:
                await self.inventory_repository.update_money(giftitem['Sender'], price)

            await self.inventory_repository.delete_giftitem(giftitem_id)
            await self.inventory_repository.update_receiptgift_result(giftitem_id, user_id, ReceiptGiftResult.Denied)
            await self.conn.on_send(ItemGiftConfirmResp.success([], AcquisitionType.Gift, expire_type))  # RTC 0, n = 0
        else:
            chest = await self.insert_chest(user_id, menu, acquisition, expire_type)
            
            await self.inventory_repository.update_giftmsg_status(giftmsg['No'], user_id, giftitem['Sender'], GiftMsgType.Accepted)
            await self.inventory_repository.delete_giftitem(giftitem_id)
            await self.inventory_repository.update_receiptgift_result(giftitem_id, user_id, ReceiptGiftResult.Accepted)

            await self.conn.on_send(ItemGiftConfirmResp.success(chest, AcquisitionType.Gift, expire_type))

    # mesma criação de baú da compra (antes havia uma cópia aqui que chamava um calc_period inexistente)
    calc_period = ItemBuyRecv.calc_period
    insert_chest = ItemBuyRecv.insert_chest
    get_field_name = ItemBuyRecv.get_field_name

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ITEM_GIFT_CONFIRM.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

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
                buf.write_uint8(0)  # sem validade: o cliente não lê u32 (TH 0x4d2a96, v440 0x4f45e8)
            else:
                buf.write_uint8(1)
                buf.write_uint32(item['period'])
            buf.write_uint8(1)  # layout do 0x6021 (v440): u8 flag + u32 Volume, u8 flag (+ u32) PlaceOrder; sem o u8 final do 0x6001
            buf.write_uint32(int(item.get('volume') or 1))
            buf.write_uint8(0)

        return cls(buf)

    @classmethod
    def error(cls, rtc: int = 4):
        """Falha: o original manda RTC 1 ou 4 (outro resultado do job); o cliente mostra o popup e fica no presente."""
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM_GIFT_CONFIRM)
        buf.write_uint16(rtc)
        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex(8)}")