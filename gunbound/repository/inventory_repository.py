from datetime import datetime, timedelta
from typing import Dict, Any, List
from gunbound.base.database import Database
from gunbound.base.helpers import seconds_until
from gunbound.base.enums import ReceiptGiftResult, AcquisitionType, ReceiptBuyType, GiftMsgType, ExpireType

class InventoryRepository:
    def __init__(self, db: Database):
        self.db = db

    async def get_menu(self, menu_id: int, acquisition: AcquisitionType, expire_type: ExpireType) -> Dict[str, Any] | None:
        """
        Retorna os itens que o usuário possui.

        Args:
            menu_id (int): O número do item.
            acquisition (AcquisitionType): Tipo de aquisição.
            expire_type (ExpireType): Tipo de expiração ("W" para semana, "M" para mês, "I" para eterno).

        Returns:
            List[Dict[str, Any]]: Lista de itens no baú do usuário.
        """

        price_field = None
        if acquisition == AcquisitionType.Gold:
            price_field = f"PriceByGoldFor{expire_type.value}"
        elif acquisition == AcquisitionType.Cash:
            price_field = f"PriceByCashFor{expire_type.value}"
        elif acquisition == AcquisitionType.Gift:
            price_field = f"PriceByGoldFor{expire_type.value}"
        else:
            raise ValueError("Acquisition inválido")

        data = await self.db.fetch_one(
            f"SELECT Item1, Period1, Volume1, Item2, Period2, Volume2, Item3, Period3, Volume3, Item4, Period4, Volume4, Item5, Period5, Volume5, {price_field} FROM Menu WHERE No=:menu_id",
            {'menu_id': menu_id}
        )
        return data
    
    async def get_giftmsg_from_giftitem(self, user_id: str, giftitem_id: int) -> List[Dict[str, Any]] | None:
        """
        Retorna a mensagem baseado no item de presente.

        Args:
            user_id (str): O identificador único do usuário.
            giftitem_id (int): O identificador do item de presente.
        """
        data = await self.db.fetch_one(
            "SELECT No, MenuId, ExpireType FROM GiftMsg WHERE Receiver=:user_id and GiftItemNo = :giftitem_id",
            {'user_id': user_id, 'giftitem_id': giftitem_id}
        )
        return data
    
    async def get_giftitem(self, user_id: str, giftitem_id: int) -> Dict[str, Any] | None:
        """
        Busca o item do presente para o usuário.

        Args:
            user_id (str): O identificador único do usuário.
            giftitem_id (int): O identificador do item de presente.
        """
        data = await self.db.fetch_one(
            "SELECT Sender, ReceiptGiftNo, Acquisition FROM GiftItem WHERE No=:giftitem_id and Receiver=:user_id",
            {'user_id': user_id, 'giftitem_id': giftitem_id}
        )
        return data
    
    async def get_chest(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retorna os itens que o usuário possui.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            List[Dict[str, Any]]: Lista de itens no baú do usuário.
        """
        items = await self.db.fetch_all(
            "SELECT c.No, c.Item, c.Wearing, c.Acquisition, c.Expire, c.Volume, c.PlaceOrder, c.Recovered, COALESCE(e.Level, 0) AS EnchantLevel, COALESCE(e.Seal, 0) AS Seal "
            "FROM Chest c LEFT JOIN ChestEnchant e ON e.No = c.No WHERE c.Owner = :user_id",
            {'user_id': user_id}
        )
        return [i | {'Expire': seconds_until(i['Expire'])} for i in items]
    
    async def get_chest_item(self, user_id: int, chest_id: int) -> Dict[str, Any] | None:
        """
        Retorna um item específico do baú.

        Args:
            user_id (str): O identificador único do usuário.
            chest_id (int): O identificador do item no baú.

        Returns:
            Dict[str, Any]|None
        """
        data = await self.db.fetch_one(
            "SELECT Item, Acquisition, Volume, Recovered, ExpireType, Expire FROM Chest WHERE No=:chest_id AND Owner=:user_id",
            {'chest_id': chest_id, 'user_id': user_id}
        )
        return data | {'Expire': seconds_until(data['Expire'])} if data else None
    
    async def get_refund_value(self, menu_id: int, acquisition: AcquisitionType) -> int | None:
        field = f"Refund_{acquisition.value}"
        data = await self.db.fetch_one(f"SELECT {field} FROM Item WHERE No=:menu_id", {'menu_id': menu_id})
        return data[field] if data else None

    async def get_cash(self, user_id: str) -> int:
        """
        Retorna a quantidade de cash do usuário.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            int: Quantidade de cash do usuário.
        """
        data = await self.db.fetch_one(
            "SELECT Cash FROM Cash WHERE Id = :user_id",
            {'user_id': user_id}
        )
        return data['Cash'] if data else 0

    async def get_money(self, user_id: str) -> int:
        """
        Retorna a quantidade de dinheiro do usuário.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            int: Quantidade de dinheiro do usuário.
        """
        data = await self.db.fetch_one(
            "SELECT Money FROM Game WHERE Id = :user_id",
            {'user_id': user_id}
        )
        return data['Money'] if data else 0

    async def insert_chest(self, user_id: str, menu_id: int, acquisition: AcquisitionType, expire_type: ExpireType, period: int | None, volume: int) -> int:
        """
        Insere um novo item no baú do usuário.

        Args:
            user_id (str): O identificador único do usuário.
            item (int): O identificador do item.
            wearing (int): Estado de uso do item.
            acquisition (AcquisitionType): Tipo de aquisição ("G" para Gold, "C" para Cash, "T" para Transfer).
            expire_type (ExpireType): Tipo de expiração ("W" para semana, "M" para mês, "I" para eterno).
            period (int|None): Período de expiração em segundos (None se expire_type for "I").
            volume (int): Quantidade do item.
        """

        return await self.db.insert('Chest', {
            'Owner': user_id,
            'Item': menu_id,
            'Acquisition': acquisition.value,
            'ExpireType': expire_type.value,
            'Expire': None if expire_type == ExpireType.Infinite else datetime.now() + timedelta(seconds=period),
            'Volume': volume,
        })
    
    async def cheapest_menus(self, lo: int, hi: int, limit: int) -> List[int]:
        """Menus de 1 item só, com código em [lo, hi) e preço em gold eterno, do mais barato ao mais caro."""
        rows = await self.db.fetch_all(
            "SELECT No FROM Menu WHERE Item1>=:lo AND Item1<:hi AND Item2 IS NULL AND PriceByGoldForI>0 "
            "ORDER BY PriceByGoldForI, No LIMIT :limit", {'lo': lo, 'hi': hi, 'limit': limit})
        return [int(r['No']) for r in rows]

    async def avatar_prices(self, lo: int, hi: int) -> List[tuple[int, int, int]]:
        """(item, gold, cash) eternos dos menus de 1 item só com código em [lo, hi): equipamento dos bots."""
        rows = await self.db.fetch_all(
            "SELECT Item1, PriceByGoldForI AS g, PriceByCashForI AS c FROM Menu WHERE Item1>=:lo AND Item1<:hi "
            "AND Item2 IS NULL AND (PriceByGoldForI>0 OR PriceByCashForI>0)", {'lo': lo, 'hi': hi})
        return [(int(r['Item1']), int(r['g'] or 0), int(r['c'] or 0)) for r in rows]

    async def insert_buy_info(self, product_version: str, menu_id: int,  price: int, asset: int, buy_type: AcquisitionType) -> None:
        """
        Insere um registro de compra na tabela BuyInfo.

        Args:
            product_version (str): A versão do produto.
            menu_id (int): ID do item comprado proveniente da tabela Menu
            price (int): O preço do item.
            asset (int): Quantidade de dinhiero que o usuário tinha antes da compra
            buy_type (str): O tipo de compra (C = Cash, G = Gold).
        """
        await self.db.execute(
            "INSERT INTO BuyInfo (SerialNo, MenuNo, Price, Asset, BuyType, Time) VALUES (:product_version, :menu_id, :price, :asset, :buy_type, :now)",
            {
                'product_version': int(product_version),
                'menu_id': menu_id,
                'price': price,
                'asset': asset,
                'buy_type': buy_type.value,
                'now': datetime.now(),
            }
        )

    async def insert_receiptbuy(self, user_id: str, menu_id: int, acquisition: AcquisitionType, price: int, buy_type: ReceiptBuyType, expire_type: ExpireType) -> int:
        """
        Insere um registro de compra na tabela ReceiptBuy.

        Args:
            user_id (str): O identificador único do usuário.
            menu_id (int): ID do item comprado proveniente da tabela Menu
            acquisition (AcquisitionType): O tipo de aquisição.
            price (int): O preço do item.
            buy_type (ExpireType): O tipo de compra ("S" para compra normal).
            expire_type (str): O tipo de expiração ("W" para semana, "M" para mês, "I" para eterno).
        """
        price_field = 'CashChecked' if acquisition == AcquisitionType.Cash else 'GoldChecked'
        return await self.db.insert('ReceiptBuy', {
            'Id': user_id,
            'MenuId': menu_id,
            price_field: price,
            'Time': datetime.now(),
            'BuyType': buy_type.value,
            'ExpireType': expire_type.value,
        })

    async def insert_receiptconsume(self, user_id: str, menu_id: int, volume: int, recovered: bool, refund: int, expire_type: ExpireType, expire: int) -> int:
        """
        Insere um registro de consumo na tabela ReceiptConsume.
        
        Args:
            user_id (str): O identificador único do usuário.
            menu_id (int): ID do item consumido proveniente da tabela Menu
            volume (int): A quantidade do item consumido.
            recovered (bool): Desconhecido
            refund (int): O valor de reembolso do item. 0 se não houver reembolso.
            expire_type (ExpireType): O tipo de expiração.
            expire (int): Tempo restante para expiração (positivo) ou a quanto tempo expirou (negativo), em segundos.  
        """
        await self.db.insert('ReceiptConsume', {
            'Id': user_id,
            'Item': menu_id,
            'Volume': volume,
            'Recovered': int(recovered),
            'Refund': refund,
            'Time': datetime.now(),
            'ExpireType': expire_type.value,
            'Expire': expire,
        })

    async def insert_giftitem(self, sender_id: str, receiver_id: str, menu_id: int, acquisition: AcquisitionType) -> int:
        """
        Insere um registro de presente na tabela GiftItem.
        Args:
            sender_id (str): O identificador único do usuário que enviou o presente.
            receiver_id (str): O identificador único do usuário que recebeu o presente.
            menu_id (int): ID do item comprado proveniente da tabela Menu
            acquisition (AcquisitionType): O tipo de aquisição.
        """
        return await self.db.insert('GiftItem', {
            'Sender': sender_id,
            'Receiver': receiver_id,
            'MenuId': menu_id,
            'Acquisition': acquisition.value,
        })
    
    async def insert_giftmsg(self, sender_id: str, receiver_id: str, menu_id: int, giftitem_id: int, message_type: str, message: str | None, expire_type: ExpireType) -> int:
        """
        Insere um registro de mensagem de presente na tabela GiftMessage.
        Args:
            sender_id (str): O identificador único do usuário que enviou a mensagem.
            receiver_id (str): O identificador único do usuário que recebeu a mensagem.
            menu_id (int): ID do item comprado proveniente da tabela Menu
            giftitem_id (int): ID do item presente proveniente da tabela GiftItem
            message_type (str): O tipo de mensagem. (G = ????)
            message (str): O conteúdo da mensagem.
            expire_type (str): O tipo de expiração ("W" para semana, "M" para mês, "I" para eterno).
        """
        return await self.db.insert('GiftMsg', {
            'Receiver': receiver_id,
            'MenuId': menu_id,
            'GiftItemNo': giftitem_id,
            'Sender': sender_id,
            'ExpireType': expire_type.value,
            'SentTime': datetime.now(),
            'Msg': message or '',
            'MsgType': getattr(message_type, 'value', message_type),
        })
    
    async def insert_receiptgift(self, sender_id: str, receiver_id: str, menu_id: int, receiver_nickname: str, result: ReceiptGiftResult, expire_type: ExpireType) -> int:
        """
        Insere um registro de mensagem de presente na tabela GiftMessage.
        Args:
            sender_id (str): O identificador único do usuário que enviou a mensagem.
            receiver_id (str): O identificador único do usuário que recebeu a mensagem.
            menu_id (int): ID do item comprado proveniente da tabela Menu
            receiver_nickname (str): O apelido do usuário no momento que recebeu o presente.
            result: (ReceiptGiftResult): Status do recibo do presente.
            expire_type (ExpireType): O tipo de expiração ("W" para semana, "M" para mês, "I" para eterno).
        """
        menu = await self.db.fetch_one("SELECT Volume1 FROM Menu WHERE No=:menu_id", {'menu_id': menu_id})
        return await self.db.insert('ReceiptGift', {
            'Id': sender_id,
            'MenuId': menu_id,
            'Volume': menu['Volume1'] if menu else None,
            'Receiver': receiver_id,
            'ReceiverNick': receiver_nickname,
            'Time': datetime.now(),
            'Result': result.value,
            'ExpireType': expire_type.value,
        })

    async def update_giftitem_receiptgift_id(self, giftitem_id: int, receiptgift_id: int) -> bool:
        """
        Atualiza o ID do recibo de presente na tabela GiftItem.
        Args:
            giftitem_id (int): ID do item presente.
            receiptgift_id (int): O ID do recibo de presente.
        """
        rowcount = await self.db.execute(
            "UPDATE GiftItem SET ReceiptGiftNo=:receiptgift_id WHERE No=:giftitem_id",
            {'receiptgift_id': receiptgift_id, 'giftitem_id': giftitem_id}
        )
        return rowcount == 1
    
    async def update_receiptbuy_receiptgift_id(self, receiptbuy_id: int, receiptgift_id: int) -> bool:
        """
        Atualiza o ID do recibo de compra na tabela ReceiptBuy.
        Args:
            receiptbuy_id (int): ID do recibo de compra.
            receiptgift_id (int): O ID do recibo de presente.
        """
        rowcount = await self.db.execute(
            "UPDATE ReceiptBuy SET ReceiptGiftNo=:receiptgift_id where No=:receiptbuy_id",
            {'receiptgift_id': receiptgift_id, 'receiptbuy_id': receiptbuy_id}
        )
        return rowcount == 1

    async def update_receiptgift_result(self, receiptgift_id: int, user_id: str, result: ReceiptGiftResult) -> bool:
        """
        Atualiza o ID do recibo de compra na tabela ReceiptBuy.
        Args:
            receiptbuy_id (int): ID do recibo de compra.
            receiptgift_id (int): O ID do recibo de presente.
        """
        rowcount = await self.db.execute(
            "UPDATE ReceiptGift SET Result=:result, ConfirmTime=:now WHERE No=:receiptgift_id AND Id=:user_id",
            {'now': datetime.now(), 'result': result.value, 'receiptgift_id': receiptgift_id, 'user_id': user_id}
        )
        return rowcount == 1
    
    async def chest_consume(self, user_id: str, chest_id: str, volume: int) -> bool:
        rowcount = await self.db.execute(
            "UPDATE Chest SET Volume=Volume-:volume WHERE No=:chest_id AND Owner=:user_id",
            {
                'volume': volume,
                'chest_id': chest_id,
                'user_id': user_id,
            }
        )
        return rowcount == 1

    async def get_enchant_rate(self, level: int) -> Dict[str, Any] | None:
        """Chances (%) de chegar a `level` no encantamento (tabela EnchantLevel do seed)."""
        return await self.db.fetch_one(
            "SELECT Level, Success, Down1, Down2, Down3, Destroy, JewelBonus FROM EnchantLevel WHERE Level=:level", {'level': level})

    async def set_enchant_level(self, chest_id: int, level: int) -> None:
        await self._set_enchant(chest_id, 'Level', level)

    async def set_seal(self, chest_id: int, seal: int) -> None:
        """Selo de avatar do WCS2 (0x7134), u32 que volta no 0x6001 e no bloco de avatar da sala."""
        await self._set_enchant(chest_id, 'Seal', seal)

    async def _set_enchant(self, chest_id: int, column: str, value: int) -> None:
        if not await self.db.execute(f"UPDATE ChestEnchant SET {column}=:v WHERE No=:c", {'v': value, 'c': chest_id}):
            await self.db.insert('ChestEnchant', {'No': chest_id, column: value})

    async def delete_chest(self, user_id: str, chest_id: int) -> bool:
        """Remove o item do baú (encantamento destruído) junto com o nível."""
        rowcount = await self.db.execute("DELETE FROM Chest WHERE No=:c AND Owner=:o", {'c': chest_id, 'o': user_id})
        await self.db.execute("DELETE FROM ChestEnchant WHERE No=:c", {'c': chest_id})
        return rowcount == 1

    async def update_place_order(self, user_id: str, places: list[tuple[int, int]]) -> int:
        """0x600A SVC_ITEM_LOCATION: posição de cada item no baú (só itens do próprio dono)."""
        total = 0
        for chest_id, place in places:
            total += await self.db.execute("UPDATE Chest SET PlaceOrder=:p WHERE No=:c AND Owner=:o", {'p': place, 'c': chest_id, 'o': user_id})
        return total

    async def update_wearing(self, user_id: str, changes: list[tuple[int, int]]) -> None:
        """0x600E: guarda o que está vestido para a próxima sessão (sala e baú leem Wearing)."""
        for chest_id, wear in changes:
            await self.db.execute("UPDATE Chest SET Wearing=:w WHERE No=:c AND Owner=:o", {'w': 1 if wear else 0, 'c': chest_id, 'o': user_id})

    async def transfer_chest(self, chest_id: int, sender_id: str, receiver_id: str, receiver_nick: str, msg: str) -> int | None:
        """
        0x6028 SVC_ITEM_GIFT (item DB 0x19 do original): passa um item C/G não recuperado do baú (vira 'T'), grava
        GiftMsg (sem MsgType, então o 0x6004 não o lista) e ReceiptGift com Item/Expire, como o original (colunas do TH em
        diante, criadas pelo init_db.py). Devolve o Item doado, ou None.
        """
        params = {'r': receiver_id, 'c': chest_id, 's': sender_id}
        transaction = await self.db.transaction()  # banco sem as colunas novas: o item não muda de dono
        try:
            if await self.db.execute(
                "UPDATE Chest SET Owner=:r, Wearing=0, Acquisition='T', PlaceOrder=0 "
                "WHERE No=:c AND Owner=:s AND Acquisition IN ('C','G') AND Recovered=0", params) <= 0:
                await transaction.rollback()
                return None
            row = await self.db.fetch_one("SELECT Item, Volume, Expire FROM Chest WHERE No=:c", {'c': chest_id})
            now = datetime.now()
            await self.db.insert('GiftMsg', {'Receiver': receiver_id, 'ItemId': row['Item'], 'Sender': sender_id,
                                             'SentTime': now, 'Msg': msg})
            await self.db.insert('ReceiptGift', {'Id': sender_id, 'Item': row['Item'], 'Expire': row['Expire'],
                                                 'Volume': row['Volume'], 'Receiver': receiver_id,
                                                 'ReceiverNick': receiver_nick, 'Time': now})
            await transaction.commit()
        except Exception:
            await transaction.rollback()
            raise
        return int(row['Item'])

    async def update_money(self, user_id: str, money: int) -> bool:
        """
        Atualiza a quantidade de dinheiro do usuário.

        Args:
            user_id (str): O identificador único do usuário.
            amount (int): A quantidade a ser adicionada (pode ser negativa para subtrair).
        """
        if money < 0:
            money = abs(money)
            rowcount = await self.db.execute(
                "UPDATE Game SET Money=Money-:money WHERE Id=:user_id AND Money>=:money",
                {'money': money, 'user_id': user_id}
            )
        else:
            rowcount = await self.db.execute(
                "UPDATE Game SET Money=Money+:money WHERE Id=:user_id",
                {'money': money, 'user_id': user_id}
            )
        return rowcount == 1

    async def update_cash(self, user_id: str, cash: int) -> bool:
        """
        Atualiza a quantidade de cash do usuário.

        Args:
            user_id (str): O identificador único do usuário.
            cash (int): A quantidade a ser adicionada (pode ser negativa para subtrair).
        """

        if cash < 0:
            cash = abs(cash)
            rowcount = await self.db.execute(
                "UPDATE Cash SET Cash=Cash-:cash WHERE Id=:user_id AND Cash>=:cash",
                {'cash': cash, 'user_id': user_id}
            )
        else:
            rowcount = await self.db.execute(
                "UPDATE Cash SET Cash=Cash+:cash WHERE Id=:user_id",
                {'cash': cash, 'user_id': user_id}
            )
        return rowcount == 1

    async def update_giftmsg_status(self, giftmsg_id: int, sender_id: str, receiver_id: str, msg_type: GiftMsgType) -> bool:
        """
        Atualiza o status da mensagem de presente do usuário.

        Args:
            user_id (str): O identificador único do usuário.
            cash (int): A quantidade a ser adicionada (pode ser negativa para subtrair).
        """

        rowcount = await self.db.execute(
            "UPDATE GiftMsg SET MsgType=:msg_type, Receiver=:receiver_id, Sender=:sender_id WHERE No=:giftmsg_id",
            {'msg_type': getattr(msg_type, 'value', msg_type), 'receiver_id': receiver_id, 'sender_id': sender_id, 'giftmsg_id': giftmsg_id}
        )
        return rowcount == 1

    async def delete_giftitem(self, giftitem_id: int) -> bool:
        """
        Deleta o item de presente da tabela GiftItem.
        Args:
            giftitem_id (int): ID do item presente.
        """
        rowcount = await self.db.execute(
            "DELETE FROM GiftItem WHERE No=:giftitem_id",
            {'giftitem_id': giftitem_id}
        )
        return rowcount == 1