from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING
from dependency_injector.providers import Configuration, Factory
from gunbound.base.enums import RoomSortList, RoomStatus, RoomOptions
from gunbound.util import synchronized

if TYPE_CHECKING:
    from gunbound.game.room import Room
    from gunbound.game.client import ClientConnection
    from gunbound.game_server import GameServer


class RoomManager:
    """
    @todo Verificar limites de salas por canal.
    """
    def __init__(self, server: 'GameServer', config: Configuration, room_factory: Factory['Room']):
        self.server = server
        self.config = config
        self.room_factory = room_factory
        self.rooms: dict[int, Room] = {}
        self.lock = asyncio.Lock()

    def size(self) -> int:
        return len(self.rooms)

    def get(self, id: int) -> Room | None:
        return self.rooms.get(id)

    @synchronized()
    async def create(self, owner: 'ClientConnection', options: RoomOptions) -> Room:
        id = next(i for i in range(len(self.rooms) + 1) if i not in self.rooms)
        self.rooms[id] = self.room_factory(room_manager=self, id=id, owner=owner, options=options)
        return self.rooms[id]

    @synchronized()
    async def destroy(self, room: Room) -> bool:
        return self.rooms.pop(room.id, None) is not None

    async def leave(self, conn: 'ClientConnection') -> Room | None:
        """Tira o jogador da sala atual e destrói a sala se ficar vazia. Retorna a sala (ou None)."""
        room = conn.room
        if room is None or await room.leave(conn) is None:
            return None
        if room.status == RoomStatus.DESTROYING:
            await self.destroy(room)
        return room

    async def get_rooms(self, sort_by: RoomSortList, current_page: int = 0, per_page: int = 9) -> list[Room]:
        """Filtra as salas pelo critério da lista e aplica paginação."""
        rooms = [r for r in self.rooms.values() if r.status != RoomStatus.DESTROYING]
        if sort_by == RoomSortList.WAITING:
            rooms = [r for r in rooms if r.status == RoomStatus.WAITING]
        start = max(0, current_page * per_page)
        return rooms[start:start + per_page]
