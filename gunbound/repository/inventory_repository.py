from typing import Dict, Any, List
from databases import Database
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
        return dict(data) if data else None
    
    async def get_giftmsg_from_giftitem(self, user_id: str, giftitem_id: int) -> List[Dict[str, Any]] | None:
        """
        Retorna a mensagem baseado no item de presente.

        Args:
            user_id (str): O identificador único do usuário.
            giftitem_id (int): O identificador do item de presente.
        """
        data = await self.db.fetch_one(
            "SELECT No, MenuId, ExpireType FROM giftmsg WHERE Receiver=:user_id and GiftItemNo = :giftitem_id",
            {'user_id': user_id, 'giftitem_id': giftitem_id}
        )
        return dict(data) if data else None
    
    async def get_giftitem(self, user_id: str, giftitem_id: int) -> Dict[str, Any] | None:
        """
        Busca o item do presente para o usuário.

        Args:
            user_id (str): O identificador único do usuário.
            giftitem_id (int): O identificador do item de presente.
        """
        data = await self.db.fetch_one(
            "SELECT Sender, ReceiptGiftNo, Acquisition FROM giftitem WHERE No=:giftitem_id and Receiver=:user_id",
            {'user_id': user_id, 'giftitem_id': giftitem_id}
        )
        return dict(data) if data else None
    
    async def get_chest(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retorna os itens que o usuário possui.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            List[Dict[str, Any]]: Lista de itens no baú do usuário.
        """
        items = await self.db.fetch_all(
            "SELECT No, Item, Wearing, Acquisition, (UNIX_TIMESTAMP(Expire) - UNIX_TIMESTAMP()) AS Expire, Volume, PlaceOrder, Recovered FROM Chest WHERE Owner = :user_id",
            {'user_id': user_id}
        )
        return [dict(i) for i in items]
    
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
            "SELECT Item, Acquisition, Volume, Recovered, ExpireType, UNIX_TIMESTAMP(Expire)-UNIX_TIMESTAMP() AS Expire FROM Chest WHERE No=:chest_id AND Owner=:user_id",
            {'chest_id': chest_id, 'user_id': user_id}
        )
        return dict(data) if data else None
    
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
            "SELECT Money FROM game WHERE Id = :user_id",
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

        if expire_type == ExpireType.Infinite:
            return await self.db.execute(
                "INSERT INTO Chest SET Owner=:user_id, Item=:menu_id, Acquisition=:acquisition, ExpireType='I', Volume=:volume",
                {
                    'user_id': user_id,
                    'menu_id': menu_id,
                    'acquisition': acquisition.value,
                    'volume': volume,
                }
            )
        else:
            return await self.db.execute(
                "INSERT INTO Chest SET Owner=:user_id, Item=:menu_id, Acquisition=:acquisition, ExpireType=:expire_type, Expire=NOW()+INTERVAL :period SECOND, Volume=:volume",
                {
                    'user_id': user_id,
                    'menu_id': menu_id,
                    'acquisition': acquisition.value,
                    'expire_type': expire_type.value,
                    'period': period,
                    'volume': volume,
                }
            )
    
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
            "INSERT INTO BuyInfo (SerialNo, MenuNo, Price, Asset, BuyType, Time) VALUES (:product_version, :menu_id, :price, :asset, :buy_type, NOW())",
            {
                'product_version': product_version,
                'menu_id': menu_id,
                'price': price,
                'asset': asset,
                'buy_type': buy_type.value,
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
        if acquisition == AcquisitionType.Cash: # Cash
            return await self.db.execute(
                "INSERT INTO ReceiptBuy SET Id=:user_id, MenuId=:menu_id, GoldChecked=:price, Time=NOW(), BuyType=:buy_type, ExpireType=:expire_type",
                {
                    'user_id': user_id,
                    'menu_id': menu_id,
                    'price': price,
                    'buy_type': buy_type.value,
                    'expire_type': expire_type.value,
                }
            )
        else: # Gold
            return await self.db.execute(
                "INSERT INTO ReceiptBuy SET Id=:user_id, MenuId=:menu_id, GoldChecked=:price, Time=NOW(), BuyType=:buy_type, ExpireType=:expire_type",
                {
                    'user_id': user_id,
                    'menu_id': menu_id,
                    'price': price,
                    'buy_type': buy_type.value,
                    'expire_type': expire_type.value,
                }
            )

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
        await self.db.execute(
            "INSERT INTO ReceiptConsume SET Id=:user_id, Item=:menu_id, Volume=:volume, Recovered=:recovered, Refund=:refund, Time=NOW(), ExpireType=:expire_type, Expire=:expire",
            {
                'user_id': user_id,
                'menu_id': menu_id,
                'volume': volume,
                'recovered': recovered,
                'refund': refund,
                'expire_type': expire_type.value,
                'expire': expire,
            }
        )

    async def insert_giftitem(self, sender_id: str, receiver_id: str, menu_id: int, acquisition: AcquisitionType) -> int:
        """
        Insere um registro de presente na tabela GiftItem.
        Args:
            sender_id (str): O identificador único do usuário que enviou o presente.
            receiver_id (str): O identificador único do usuário que recebeu o presente.
            menu_id (int): ID do item comprado proveniente da tabela Menu
            acquisition (AcquisitionType): O tipo de aquisição.
        """
        return await self.db.execute(
            "INSERT INTO GiftItem SET Sender=:sender_id, MenuId=:menu_id, Acquisition=:acquisition, Receiver=:receiver_id",
            {
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'menu_id': menu_id,
                'acquisition': acquisition.value,
            }
        )
    
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
        return await self.db.execute(
            "INSERT INTO GiftMsg SET Receiver=:receiver_id, MenuId=:menu_id, GiftItemNo=:giftitem_id, Sender=:sender_id, ExpireType=:expire_type, SentTime=NOW(), Msg=:message, MsgType=:message_type",
            {
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'menu_id': menu_id,
                'giftitem_id': giftitem_id,
                'message_type': message_type,
                'message': message,
                'expire_type': expire_type.value,
            }
        )
    
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
        return await self.db.execute(
            "INSERT INTO ReceiptGift (Id, MenuId, Volume, Receiver, ReceiverNick, Time, Result, ExpireType) SELECT :sender_id, :menu_id, Volume1, :receiver_id, :receiver_nickname, NOW(), :result, :expire_type FROM menu WHERE No=:menu_id",
            {
                'sender_id': sender_id,
                'menu_id': menu_id,
                'receiver_id': receiver_id,
                'receiver_nickname': receiver_nickname,
                'result': result.value,
                'expire_type': expire_type.value,
            }
        )

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
            "UPDATE ReceiptGift SET Result=:result, ConfirmTime=NOW() WHERE No=:receiptgift_id AND Id=:user_id",
            {'result': result.value, 'receiptgift_id': receiptgift_id, 'user_id': user_id}
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
                "UPDATE cash SET Cash=Cash-:cash WHERE Id=:user_id AND Cash>=:cash",
                {'cash': cash, 'user_id': user_id}
            )
        else:
            rowcount = await self.db.execute(
                "UPDATE cash SET Cash=Cash+:cash WHERE Id=:user_id",
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
            {'msg_type': msg_type, 'receiver_id': receiver_id, 'sender_id': sender_id, 'giftmsg_id': giftmsg_id}
        )
        return rowcount == 1

    async def delete_giftitem(self, giftitem_id: int) -> bool:
        """
        Deleta o item de presente da tabela GiftItem.
        Args:
            giftitem_id (int): ID do item presente.
        """
        result = await self.db.execute(
            "DELETE FROM GiftItem WHERE No=:giftitem_id",
            {'giftitem_id': giftitem_id}
        )
        return result.rowcount == 1