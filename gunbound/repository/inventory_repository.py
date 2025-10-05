from gunbound.base.managers import DatabaseManager
from typing import Dict, Any, List

class InventoryRepository:
    def __init__(self):
        self.db = DatabaseManager.get_instance()

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