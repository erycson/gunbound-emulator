import asyncio
from gunbound.game.client import ClientConnection
from gunbound.util import synchronized

class Channel:
    """
    @todo Verificar limites de usuários por canal.
    """
    def __init__(self, manager, id: int):
        self.id = id
        self.manager = manager
        self.clients: dict[int, ClientConnection] = {}
        self.lock = asyncio.Lock()
    
    def size(self) -> int:
        return len(self.clients)

    @synchronized()
    async def add(self, client: ClientConnection) -> bool:
        if client.id in self.clients:
            # Usuário está tentando entrar no mesmo canal novamente
            return False
        elif client.channel is not None:
            # Sai do canal anterior
            await client.channel.remove(client)

        self.clients[client.id] = client
        client.channel = self
        return True
    
    @synchronized()
    async def remove(self, client: ClientConnection) -> bool:
        if client.id not in self.clients:
            return False
    
        del self.clients[client.id]
        client.channel = None
        return True