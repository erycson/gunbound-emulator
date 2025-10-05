from __future__ import annotations
import asyncio
import bisect
from typing import TYPE_CHECKING
from gunbound.util import synchronized
from gunbound.base.protocol import BasePackageSend
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
        self.sorted_clients: list[int] = []
        self.lock = asyncio.Lock()

    @synchronized()
    async def add(self, client: 'ClientConnection') -> bool:
        if client.id in self.clients or len(self.sorted_clients) >= 255:
            return False
        
        self.clients[client.id] = client

        pos = self._find_insertion_point(client.id)
        self.sorted_clients.insert(pos, client.id)

        return True

    @synchronized()
    async def remove(self, client: 'ClientConnection') -> bool:
        if client.id not in self.clients:
            return False
        del self.clients[client.id]
        self.sorted_clients.remove(client.id)

        return True

    @synchronized()
    async def get_all(self) -> list[tuple[int, 'ClientConnection']]:
        """
        Retorna a lista de (posição, conexão) ordenada por ID de usuário.
        """
        return [(pos, self.clients[client_id]) for pos, client_id in enumerate(self.sorted_clients)]

    async def broadcast(self, packet, onlys: None | list[int] = None, excepts: None | list[int] = None) -> None:
        """
        Envia um ou vários pacotes para todos os usuários conectados no canal de forma assíncrona e de alta performance, sem aguardar conclusão.
        packets pode ser um BasePackageSend único ou uma lista deles.
        """
        clients = await self.get_all()
        for _, client in clients:
            if onlys and client.id not in onlys:
                continue
            if excepts and client.id in excepts:
                continue
            asyncio.create_task(client.on_send(packet))

    def size(self) -> int:
        return len(self.clients)

    def get_client_position(self, client: 'ClientConnection') -> int | None:
        """
        Retorna a posição do cliente na lista ordenada, ou -1 se não encontrado.
        """
        try:
            return self.sorted_clients.index(client.id)
        except ValueError:
            return None

    def get_highest_channel_position(self) -> int:
        """
        Retorna a posição mais alta ocupada no canal
        Como positions são 0 a len-1, é len-1 ou 0 se vazio.
        """
        return max(0, len(self.sorted_clients) - 1)
    
    def _find_insertion_point(self, conn_id: int) -> int:
        """
        Versão otimizada usando bisect, que replica a lógica da função C sub_40F840.
        bisect.bisect_left com lo=0 e hi=min(255, len) limita a busca sem erro de índice.
        """
        hi = min(255, len(self.sorted_clients))
        return bisect.bisect_left(self.sorted_clients, conn_id, 0, hi)