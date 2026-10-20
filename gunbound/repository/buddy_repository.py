from datetime import datetime
from typing import List, Dict, Any, Optional
from gunbound.base.database import Database

# Dados de um usuário como o BuddyServ manda: Id, apelido, guild e grade (u16 depois da guild no 0x1011/0x3001)
_USER = ("SELECT u.Id, u.Nickname, u.Password, g.Guild, g.TotalGrade FROM User u "
         "LEFT JOIN Game g ON g.Id = u.Id")
_PUBLIC = "SELECT u.Id, u.Nickname, g.Guild, g.TotalGrade FROM User u LEFT JOIN Game g ON g.Id = u.Id"


class BuddyRepository:
    """Tabelas do BuddyServ original: BuddyList(Id, Category, Buddy) e packet (mensagens guardadas para quem está offline)."""

    def __init__(self, db: Database):
        self.db = db

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self.db.fetch_one(_USER + " WHERE u.Id = :id", {'id': user_id})

    async def get_buddies(self, user_id: str) -> List[Dict[str, Any]]:
        return await self.db.fetch_all(
            "SELECT b.Buddy, b.Category, u.Nickname, g.Guild, g.TotalGrade FROM BuddyList b "
            "JOIN User u ON u.Id = b.Buddy LEFT JOIN Game g ON g.Id = b.Buddy WHERE b.Id = :id ORDER BY b.Category", {'id': user_id})

    async def game_session_ip(self, user_id: str) -> Optional[bytes]:
        """IP (4 bytes, ordem de rede) do último login no game, só se ele ainda está no CurrentUser: o Buddy do v584
        não manda senha, então o servidor aceita só quem está no game vindo do mesmo IP."""
        row = await self.db.fetch_one(
            "SELECT l.Ip FROM CurrentUser c JOIN LoginLog l ON l.Id = c.Id WHERE c.Id = :id ORDER BY l.Time DESC LIMIT 1",
            {'id': user_id})
        return int(row['Ip']).to_bytes(4, 'little') if row else None  # LoginLog guarda inet_aton lido em little-endian

    async def buddy_of(self, user_id: str) -> List[str]:
        """Quem tem user_id na própria lista (para avisar que ele entrou ou saiu)."""
        rows = await self.db.fetch_all("SELECT Id FROM BuddyList WHERE Buddy = :id", {'id': user_id})
        return [r['Id'] for r in rows]

    async def add(self, user_id: str, buddy: str, category: str) -> bool:
        if await self.db.fetch_one("SELECT Id FROM BuddyList WHERE Id = :id AND Buddy = :buddy", {'id': user_id, 'buddy': buddy}):
            return False
        await self.db.insert('BuddyList', {'Id': user_id, 'Category': category, 'Buddy': buddy})
        return True

    async def remove(self, user_id: str, buddy: str) -> bool:
        return await self.db.execute("DELETE FROM BuddyList WHERE Id = :id AND Buddy = :buddy",
                                     {'id': user_id, 'buddy': buddy}) > 0

    async def set_category(self, user_id: str, buddies: List[str], category: str) -> None:
        for buddy in buddies:
            await self.db.execute("UPDATE BuddyList SET Category = :cat WHERE Id = :id AND Buddy = :buddy",
                                  {'cat': category, 'id': user_id, 'buddy': buddy})

    async def rename_category(self, user_id: str, old: str, new: str) -> None:
        await self.db.execute("UPDATE BuddyList SET Category = :new WHERE Id = :id AND Category = :old",
                              {'new': new, 'id': user_id, 'old': old})

    async def search(self, nickname: str, user_id: str, offset: int, count: int) -> List[Dict[str, Any]]:
        """0x4000 do original: prefixo de Id e/ou de apelido, LIMIT offset,count (os dois vazios não busca nada)."""
        where, values = [], {'offset': offset, 'count': count}
        if user_id:
            where.append("u.Id LIKE :id")
            values['id'] = f"{user_id}%"
        if nickname:
            where.append("u.Nickname LIKE :nick")
            values['nick'] = f"{nickname}%"
        if not where or not count:
            return []
        return await self.db.fetch_all(_PUBLIC + " WHERE " + " AND ".join(where) + " LIMIT :count OFFSET :offset", values)

    async def save_packet(self, receiver: str, sender: str, code: int, body: bytes) -> Optional[int]:
        return await self.db.insert('packet', {'Receiver': receiver, 'Sender': sender, 'Code': code,
                                               'Body': body, 'Time': datetime.now()})

    async def get_packets(self, receiver: str) -> List[Dict[str, Any]]:
        return await self.db.fetch_all(
            "SELECT p.SerialNo, p.Sender, p.Code, p.Body, p.Time, u.Nickname FROM packet p "
            "LEFT JOIN User u ON u.Id = p.Sender WHERE p.Receiver = :id ORDER BY p.SerialNo", {'id': receiver})

    async def delete_packets(self, receiver: str, serials: List[int]) -> None:
        for serial in serials:
            await self.db.execute("DELETE FROM packet WHERE Receiver = :id AND SerialNo = :no", {'id': receiver, 'no': serial})
