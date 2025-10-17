from typing import List, Dict, Any, Optional
from databases import Database

class UserRepository:
    def __init__(self, db: Database):
        self.db = db

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
            "SELECT Id, User, Password, Nickname, Gender, User_Level, Authority, Authority2, (CASE WHEN RestrictTime = '0000-00-00 00:00:00' THEN NULL ELSE RestrictTime END) as RestrictTime FROM User WHERE Id = :user_id",
            {'user_id': user_id}
        )
        return dict(data) if data else None

    async def get_gender(self, user_id: str) -> int | None:
        """
        Busca dados básicos do perfil do usuário das tabelas User e gbwc.user.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            int: Sexo do usuário, 0 = Masculino, 1 = Feminino.
        """
        data = await self.db.fetch_one("SELECT Gender FROM User WHERE Id=:user_id", {'user_id': user_id})
        return data.get('Gender') if data else None

    async def find_by_nickname(self, nickname: str) -> List[Dict[str, Any]]:
        """
        Pesquisa usuários pelo apelido (nickname).

        Args:
            nickname (str): O apelido do usuário.

        Returns:
            Optional[Dict[str, Any]]: Dados do perfil do usuário ou None se não encontrado.
        """
        data = await self.db.fetch_all(
            "SELECT Id, Nickname FROM user WHERE Nickname IN (:nickname) LIMIT 100",
            {'nickname': nickname}
        )
        
        return [dict(d) for d in data] if data else []

    async def get_game(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca estatísticas do jogo da tabela game.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            Optional[Dict[str, Any]]: Dados das estatísticas do jogo ou None se não encontrado.
        """
        data = await self.db.fetch_one(
            "SELECT Guild, TotalGrade, SeasonGrade, MemberCount, TotalRank, SeasonRank, GuildRank, AccumShot, AccumDamage, TotalScore, SeasonScore, Money, EventScore0, EventScore1, EventScore2, EventScore3, (CASE WHEN GiftProhibitTime = '0000-00-00 00:00:00' THEN NULL ELSE GiftProhibitTime END) AS GiftProhibitTime, ClientData, Country, CountryGrade, CountryRank FROM game WHERE Id = :user_id",
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
    
    async def update_clientdata(self, user_id: str, client_data: bytes) -> bool:
        """
        Atualiza os dados do cliente para o usuário.

        Args:
            user_id (str): O identificador único do usuário.
            client_data (bytes): Dados do cliente a serem atualizados.

        Returns:
            bool: True se a atualização foi bem-sucedida, False caso contrário.
        """
        result = await self.db.execute(
            "UPDATE Game SET ClientData = :client_data, LastUpdateTime=NOW() WHERE Id = :user_id",
            {'client_data': client_data, 'user_id': user_id}
        )
        return result > 0