from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from gunbound.base.enums import RoomStatus, RoomOptions
from gunbound.util import synchronized

if TYPE_CHECKING:
    from gunbound.base.protocol import BasePackageSend
    from gunbound.game.client import ClientConnection
    from gunbound.game.managers import RoomManager


@dataclass
class RoomPlayer:
    conn: 'ClientConnection'
    slot: int
    team: int = 0      # 0 = A, 1 = B
    ready: bool = False


class Room:
    def __init__(self, room_manager: 'RoomManager', id: int, owner: 'ClientConnection', options: RoomOptions):
        self.id = id
        self.room_manager = room_manager
        self.options: RoomOptions = options
        self.status: RoomStatus = RoomStatus.WAITING
        self.players: dict[int, RoomPlayer] = {}   # conn.id -> jogador
        self.owner: 'ClientConnection' = owner
        self.lock = asyncio.Lock()
        self.players[owner.id] = RoomPlayer(owner, slot=0, team=0)
        owner.room = self

    def player_count(self) -> int:
        return len(self.players)

    def player(self, conn: 'ClientConnection') -> RoomPlayer | None:
        return self.players.get(conn.id)

    def sorted_players(self) -> list[RoomPlayer]:
        return sorted(self.players.values(), key=lambda p: p.slot)

    def is_full(self) -> bool:
        return self.player_count() >= self.options.max_players()

    @synchronized()
    async def join(self, conn: 'ClientConnection') -> RoomPlayer | None:
        """Adiciona o jogador no primeiro slot livre, no time com menos jogadores."""
        if self.status != RoomStatus.WAITING or self.is_full() or conn.id in self.players:
            return None
        used = {p.slot for p in self.players.values()}
        slot = next(i for i in range(self.options.max_players()) if i not in used)
        team_a = sum(1 for p in self.players.values() if p.team == 0)
        player = RoomPlayer(conn, slot=slot, team=0 if team_a <= self.player_count() - team_a else 1)
        self.players[conn.id] = player
        conn.room = self
        return player

    @synchronized()
    async def leave(self, conn: 'ClientConnection') -> RoomPlayer | None:
        """Remove o jogador. Retorna o jogador removido; passa o dono para o próximo ou destrói a sala vazia."""
        player = self.players.pop(conn.id, None)
        if player is None:
            return None
        conn.room = None
        if not self.players:
            self.status = RoomStatus.DESTROYING
        elif self.owner is conn:
            self.owner = self.sorted_players()[0].conn
        return player

    async def broadcast(self, packet: 'BasePackageSend', excepts: list[int] | None = None) -> None:
        for player in list(self.players.values()):
            if excepts and player.conn.id in excepts:
                continue
            asyncio.create_task(player.conn.on_send(packet.clone()))
