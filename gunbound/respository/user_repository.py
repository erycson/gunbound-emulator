from typing import List, Dict, Any, Optional
from gunbound.base.managers import DatabaseManager

class UserRepository:
    """
    Repositório para operações de banco de dados relacionadas ao usuário.

    Esta classe lida com a busca e manipulação de dados do usuário, incluindo perfil,
    estatísticas do jogo, registros, inventário e verificações de segurança. Ela orquestra
    múltiplos sub-repositórios para domínios específicos.

    Attributes:
        db: Instância de conexão com o banco de dados.
    """

    def __init__(self):
        self.db = DatabaseManager.get()

    async def logout(self, user_id: str, context: int) -> bool:
        """
        Lida com o logout do usuário removendo-o dos usuários atuais.

        Args:
            user_id (str): O identificador único do usuário.
            context (int): Identificador de contexto da sessão.

        Returns:
            bool: True se logout bem-sucedido, False caso contrário.
        """
        result = await self.db.execute(
            "DELETE FROM CurrentUser WHERE Id = :user_id AND Context = :context",
            {'user_id': user_id, 'context': context}
        )
        return result > 0

    async def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca dados básicos do perfil do usuário das tabelas User e gbwc.user.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            Optional[Dict[str, Any]]: Dados do perfil do usuário ou None se não encontrado.
        """
        data = await self.db.fetch_one(
            "SELECT Id, User, Password, Nickname, Gender, User_Level, Authority, Authority2, RestrictTime FROM User WHERE Id = :user_id",
            {'user_id': user_id}
        )
        return dict(data) if data else None

    async def get_game(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca estatísticas do jogo da tabela game.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            Optional[Dict[str, Any]]: Dados das estatísticas do jogo ou None se não encontrado.
        """
        data = await self.db.fetch_one(
            "SELECT Guild, TotalGrade, SeasonGrade, MemberCount, TotalRank, SeasonRank, GuildRank, AccumShot, AccumDamage, TotalScore, SeasonScore, Money, EventScore0, EventScore1, EventScore2, EventScore3, GiftProhibitTime, ClientData, Country, CountryGrade, CountryRank FROM game WHERE Id = :user_id",
            {'user_id': user_id}
        )
        return dict(data) if data else None

    async def get_gift_msgs(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Busca mensagens de presente para o usuário.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            List[Dict[str, Any]]: Lista de mensagens de presente.
        """
        msgs = await self.db.fetch_all(
            "SELECT No, MenuId, Sender, SentTime, Msg, MsgType, ExpireType, GiftItemNo FROM GiftMsg WHERE Receiver = :user_id",
            {'user_id': user_id}
        )
        return [dict(m) for m in msgs]
    
    async def update_client_data(self, user_id: str, client_data: bytes) -> bool:
        """
        Atualiza os dados do cliente para o usuário.

        Args:
            user_id (str): O identificador único do usuário.
            client_data (bytes): Dados do cliente a serem atualizados.

        Returns:
            bool: True se a atualização foi bem-sucedida, False caso contrário.
        """
        # FF030102FF06FF0A24
        # if len(client_data) > 100:
        #     client_data = client_data[:100]
        # elif len(client_data) < 100:
        #     client_data = client_data + b'\x00' * (100 - len(client_data))
        
        result = await self.db.execute(
            "UPDATE Game SET ClientData = :client_data, LastUpdateTime=NOW() WHERE Id = :user_id",
            {'client_data': client_data, 'user_id': user_id}
        )
        return result > 0