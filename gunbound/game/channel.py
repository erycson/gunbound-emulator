from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING
from gunbound.util import synchronized
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection

class Channel:
    """
    @todo Verificar limites de usuários por canal.
    @todo Verificar limites de salas por canal.
    """
    def __init__(self, manager, id: int):
        self.id = id
        self.clients: dict[int, 'ClientConnection'] = {}
        self.lock = asyncio.Lock()

    @synchronized()
    async def add(self, client: 'ClientConnection') -> bool:
        if client.id in self.clients:
            return False
        self.clients[client.id] = client
        return True

    @synchronized()
    async def remove(self, client: 'ClientConnection') -> bool:
        if client.id not in self.clients:
            return False
        del self.clients[client.id]
        return True

    def size(self) -> int:
        return len(self.clients)