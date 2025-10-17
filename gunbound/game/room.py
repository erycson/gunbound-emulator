from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING
from gunbound.base.enums import RoomStatus, RoomOptions
from gunbound.util import synchronized

if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection
    from gunbound.game.managers import RoomManager

class Room:
    def __init__(self, room_manager: 'RoomManager', id: int, owner: 'ClientConnection', options: RoomOptions):
        self.id = id
        self.room_manager = room_manager
        self.owner = owner
        self.options: RoomOptions = options
        self.status: RoomStatus = RoomStatus.WAITING
        self.players: dict[int, 'ClientConnection'] = {0: owner} | {i: None for i in range(1, options.max_players() - 1)}
        self.lock = asyncio.Lock()
    
    def player_count(self) -> int:
        return sum(1 for player in self.players.values() if player is not None)
    
    @synchronized()
    async def join(self, conn: 'ClientConnection', position: int) -> bool:
        if self.status != RoomStatus.WAITING:
            return False
        if self.players[position] is not None:
            return False
        self.players[position] = conn
    
    @synchronized()
    async def kick_position(self, position: int) -> bool:
        if self.status != RoomStatus.WAITING:
            return False
        if position not in self.players:
            return False
        await self._remove_player(position)
        return True
    
    @synchronized()
    async def kick_player(self, conn: 'ClientConnection'):
        position = next((pos for pos, client in self.players.items() if client == conn), None)
        if position is not None:
            await self._remove_player(position)

    @synchronized()
    async def close(self) -> bool:
        """Fecha a sala, expulsando todos os jogadores e limpando recursos."""
        pass

    async def _remove_player(self, position: int):
        """Expulsa um jogador da sala. Implementa o envio do pacote de remoção"""
        if position not in self.players or self.players[position] is None:
            return

        player = self.players[position]
        player.room = None
        self.players[position] = None

        if self.owner == player:
            self.owner = next((p for p in self.players.values() if p is not None and p != player), None)
            if self.owner is None:
                await self.room_manager.destroy(self)

    async def _destroy(self):
        if self.status == RoomStatus.DESTROYING:
            return
        self.status = RoomStatus.DESTROYING

        """Destrói a sala e remove todos os jogadores."""
        for position, player in self.players.items():
            if player is not None:
                await self._remove_player(position)

        await self.channel.destroy(self)
