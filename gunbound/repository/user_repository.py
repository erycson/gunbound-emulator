from datetime import datetime
from typing import List, Dict, Any, Optional
from gunbound.base.database import Database
from gunbound.base.helpers import to_datetime

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
            "SELECT Id, User, Password, Nickname, Gender, User_Level, Authority, Authority2, RestrictTime FROM User WHERE Id = :user_id",
            {'user_id': user_id}
        )
        return data | {'RestrictTime': to_datetime(data['RestrictTime'])} if data else None

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
            "SELECT Id, Nickname FROM User WHERE Nickname IN (:nickname) LIMIT 100",
            {'nickname': nickname}
        )
        
        return data

    async def get_game(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca estatísticas do jogo da tabela game.

        Args:
            user_id (str): O identificador único do usuário.

        Returns:
            Optional[Dict[str, Any]]: Dados das estatísticas do jogo ou None se não encontrado.
        """
        data = await self.db.fetch_one(
            "SELECT Guild, TotalGrade, SeasonGrade, MemberCount, TotalRank, SeasonRank, GuildRank, AccumShot, AccumDamage, TotalScore, SeasonScore, Money, EventScore0, EventScore1, EventScore2, EventScore3, GiftProhibitTime, ClientData, Country, CountryGrade, CountryRank FROM Game WHERE Id = :user_id",
            {'user_id': user_id}
        )
        if not data:
            return None
        client_data = data['ClientData']
        if isinstance(client_data, str):  # Bancos antigos guardam ClientData como varchar
            client_data = client_data.encode('latin-1', errors='replace')
        return data | {'GiftProhibitTime': to_datetime(data['GiftProhibitTime']), 'ClientData': bytes(client_data or b'')}

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
        return [m | {'SentTime': to_datetime(m['SentTime'])} for m in msgs]
    
    async def delete_gift_msgs(self, nos: list[int]) -> int:
        """Apaga os avisos A/D já entregues pelo 0x6032 (como o original, logo depois do SELECT do 0x6004)."""
        keys = {f'n{i}': int(n) for i, n in enumerate(nos)}
        return await self.db.execute(f"DELETE FROM GiftMsg WHERE No IN ({', '.join(':' + k for k in keys)})", keys) if keys else 0

    async def get_nicknames(self, user_ids: list[str]) -> List[Dict[str, Any]]:
        """0x1021 SVC_USER_NICK: Id -> Nickname de vários usuários."""
        if not user_ids:
            return []
        keys = {f'u{i}': u for i, u in enumerate(user_ids)}
        return await self.db.fetch_all(f"SELECT Id, Nickname FROM User WHERE Id IN ({', '.join(':' + k for k in keys)})", keys)

    async def set_restrict_time(self, user_id: str, until: datetime) -> bool:
        """/ban: grava RestrictTime (o login recusa enquanto não passar)."""
        result = await self.db.execute("UPDATE User SET RestrictTime=:until WHERE Id=:user_id", {'until': until, 'user_id': user_id})
        return result > 0

    async def add_score(self, user_id: str, score: int) -> bool:
        """Soma GP da partida em TotalScore e SeasonScore (atômico no banco)."""
        result = await self.db.execute(
            "UPDATE Game SET TotalScore=TotalScore+:score, SeasonScore=SeasonScore+:score, LastUpdateTime=:now WHERE Id=:user_id",
            {'score': int(score), 'now': datetime.now(), 'user_id': user_id}
        )
        return result > 0

    async def insert_abnormal_update(self, master: str, user_id: str, score: int, money: int) -> None:
        """Log ANU do original: INSERT AbnormalUpdate (Master, ID, ScoreDelta, MoneyDelta, Time)."""
        await self.db.execute(
            "INSERT INTO AbnormalUpdate (Master, ID, ScoreDelta, MoneyDelta, Time) VALUES (:master, :id, :score, :money, :now)",
            {'master': master, 'id': user_id, 'score': max(-32768, min(32767, int(score))), 'money': int(money), 'now': datetime.now()}
        )

    async def add_slot_tokens(self, user_id: str, delta: int) -> bool:
        """Fichas do caça-níquel WCS2; não deixa ficar negativo."""
        # shortcut: usa a coluna EventScore2 (sem uso) em vez de coluna própria
        result = await self.db.execute("UPDATE Game SET EventScore2=EventScore2+:d WHERE Id=:user_id AND EventScore2+:d>=0",
                                       {'d': int(delta), 'user_id': user_id})
        return result > 0

    POINTS = frozenset({'DiscountPoints', 'RenaPoints', 'TotalScore'})  # colunas do Game em db/linked.sql

    async def add_points(self, user_id: str, column: str, delta: int) -> bool:
        """Pontos da loja WCS2 (desconto/Rena); não deixa ficar negativo."""
        assert column in self.POINTS
        result = await self.db.execute(f"UPDATE Game SET {column}={column}+:d WHERE Id=:user_id AND {column}+:d>=0",
                                       {'d': int(delta), 'user_id': user_id})
        return result > 0

    async def get_points(self, user_id: str, column: str) -> int:
        assert column in self.POINTS
        row = await self.db.fetch_one(f"SELECT {column} FROM Game WHERE Id=:user_id", {'user_id': user_id})
        return int(row[column]) if row else 0

    async def set_tutorial(self, user_id: str, lessons: int) -> bool:
        """Progresso do tutorial WCS2 (lições liberadas, 0..9); só avança."""
        # shortcut: usa a coluna EventScore3 (sem uso) em vez de coluna própria, criar Game.Tutorial se precisar do EventScore3
        result = await self.db.execute("UPDATE Game SET EventScore3=:n WHERE Id=:user_id AND EventScore3<:n", {'n': lessons, 'user_id': user_id})
        return result > 0

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
            "UPDATE Game SET ClientData = :client_data, LastUpdateTime=:now WHERE Id = :user_id",
            {'client_data': bytes(client_data), 'now': datetime.now(), 'user_id': user_id}
        )
        return result > 0

    async def get_ready_items(self, user_id: str) -> bytes | None:
        """WCS2: itens da sala de espera (0x6051), como o cliente mandou no 0x6052."""
        row = await self.db.fetch_one("SELECT ReadyItems FROM Game WHERE Id = :user_id", {'user_id': user_id})
        data = row and row['ReadyItems']
        return (data.encode('latin-1') if isinstance(data, str) else bytes(data)) if data else None

    async def set_ready_items(self, user_id: str, data: bytes) -> bool:
        return await self.db.execute("UPDATE Game SET ReadyItems = :data WHERE Id = :user_id",
                                     {'data': bytes(data), 'user_id': user_id}) > 0