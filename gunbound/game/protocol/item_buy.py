from __future__ import annotations
from typing import TYPE_CHECKING
from gunbound.base.database import Database
from dependency_injector.wiring import Provide, inject
from dependency_injector.providers import Configuration
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.base.enums import AcquisitionType, ReceiptBuyType, ExpireType
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.repository import InventoryRepository
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_ITEM_BUY.value)
@inject
class ItemBuyRecv(BasePackageRecv):

    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        db: Database = Provide['database'],
        config: Configuration = Provide['config'],
        inventory_repository: 'InventoryRepository' = Provide['inventory_repository']
    ):
        self.buf = buf
        self.conn = conn
        self.db = db
        self.config = config
        self.inventory_repository = inventory_repository

    async def process(self):
        """
        @todo Falta implementar verificação de compra de item repetido (ex: comprar 2 vezes o mesmo item Cash eterno)
        @todo Falta implementar códigos de erros
        """
        data = self.conn.decrypt(self.buf.read_bytes())
        buf = BinaryReader(data)

        command = (buf.read_int32() - 0x8631607E) & 0xFFFFFFFF
        if command != ClientPacket.CLI_ITEM_BUY.value:
            return

        print(f"[{self.conn.addr}] ItemBuy corpo: {data.hex(' ')}")
        user_id = self.conn.data['profile']['Id']
        menu_no = buf.read_uint32()
        acquisition = AcquisitionType.try_parse_int(buf.read_uint8())
        expire_type = ExpireType.try_parse_int(buf.read_uint8())
        _ = buf.read_bytes(6) # Desconhecido, mas parece ser sempre os mesmos valores para a mesma compra

        if acquisition is None or expire_type is None:
            return await self.fail(f"tipo inválido menu={menu_no}")

        menu = await self.inventory_repository.get_menu(menu_no, acquisition, expire_type)
        
        if not menu:
            return await self.fail(f"menu {menu_no} não existe")
        price = menu.get(self.get_field_name(acquisition, expire_type))
        if price is None:
            return await self.fail(f"menu {menu_no} sem preço {acquisition}/{expire_type}")
        # WCS2: desconto escolhido no 0x7118 (wcs2/shop.py); trunca como o cliente
        num, den = self.conn.data.get('shop_discount', (1, 1))
        price = price * num // den

        asset = None
        if acquisition == AcquisitionType.Cash:
            asset = await self.inventory_repository.get_cash(user_id) or 0
            if asset < price:
                return await self.fail(f"cash insuficiente {asset} < {price} (menu {menu_no})")
        elif acquisition == AcquisitionType.Gold:
            asset = await self.inventory_repository.get_money(user_id) or 0
            if asset < price:
                return await self.fail(f"gold insuficiente {asset} < {price} (menu {menu_no})")
        else:
            return await self.fail(f"aquisição inválida {acquisition}")

        transaction = await self.db.transaction()
        try:
            # Insere o item no inventário
            chest = await self.insert_chest(user_id, menu, acquisition, expire_type)

            # Insere o recibo da compra
            await self.inventory_repository.insert_receiptbuy(user_id, menu_no, acquisition, price, ReceiptBuyType.Self, expire_type)

            # Desconta o ativo (cash ou gold)
            if acquisition == "C":
                if not await self.inventory_repository.update_cash(user_id, -price):
                    await transaction.rollback()
                    return await self.fail("falha ao descontar cash")
            elif acquisition == "G":
                if not await self.inventory_repository.update_money(user_id, -price):
                    await transaction.rollback()
                    return await self.fail("falha ao descontar gold")

            if acquisition == AcquisitionType.Cash:
                await self.inventory_repository.insert_buy_info(self.config['product_version'], menu_no, price, asset, acquisition)
            
            await transaction.commit()

            await self.conn.on_send(ItemBuyResp.success(chest, acquisition, expire_type))
        except Exception as e:
            await transaction.rollback()
            raise e

    async def fail(self, reason: str):
        """Sem resposta o cliente fica preso na janela de compra; RTC != 0 fecha com erro."""
        print(f"[{self.conn.addr}] Compra recusada: {reason}")
        await self.conn.on_send(ItemBuyResp.error())

    def calc_period(self, expire_type: str, period: int) -> int | None:
        if expire_type == "W":
            return 7 * period
        elif expire_type == "M":
            return 30 * period
        else: # I
            return None

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
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class ItemBuyResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, chest: list[dict], acquisition: AcquisitionType, expire_type: str):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM_BUY)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint16(len(chest))

        for item in chest:
            buf.write_uint32(item['chest_id'])
            buf.write_uint32(item['item_no'])
            buf.write_uint8(0) # Desconhecido
            buf.write_char(acquisition.value)
            if expire_type == "I":
                buf.write_uint8(0)  # sem validade: o cliente não lê u32 (TH 0x4d2a96, v440 0x4f45e8)
            else:
                buf.write_uint8(1)
                buf.write_uint32(item['period'])
            buf.write_uint8(1) # Desconhecido
            buf.write_uint8(1) # Desconhecido
            buf.write_uint32(10) # Desconhecido

        return cls(buf)

    @classmethod
    def error(cls, code: int = 1):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM_BUY)
        buf.write_uint16(code)
        return cls(buf)

    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex(8)}")