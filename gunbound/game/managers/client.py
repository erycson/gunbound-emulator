import time
import random
import asyncio
from gunbound.game.client import ClientConnection
from gunbound.util import synchronized

""""
Gerencia as conexões dos clientes.

Isso foi implementado, pois, diferente do Broker, que possui regras mais simples, o GameServer precisa manter 
uma grande quantidade de regras, e para separar responsabilidades, foi decidido criar esse manager.
"""
class ClientManager:
    _instance = None
    
    def __init__(self):
        self.clients: dict[int, ClientConnection] = {}  # Corrigido para dict
        self.lock = asyncio.Lock()
        self.rand_seed: int = 1

    @classmethod
    def initialize(cls):
        if cls._instance is not None:
            raise RuntimeError("ClientManager já inicializado!")

        cls._instance = cls()
        return cls._instance

    @classmethod
    def get(cls):
        if cls._instance is None:
            raise RuntimeError("ClientManager não inicializado!")
        return cls._instance
    
    def size(self) -> int:
        return len(self.clients)
    
    @synchronized()
    async def add(self, server, reader, writer):
        prng_seed = int(time.time() + id(self)) & 0xFFFFFFFF
        client = ClientConnection(server, self, prng_seed, self.generate_id(), reader, writer)
        client.task = asyncio.create_task(client.handler())
        self.clients[client.id] = client

    @synchronized()
    async def remove(self, client: ClientConnection) -> bool:
        if client.id in self.clients:
            del self.clients[client.id]
            return True
        return False

    def generate_id(self) -> int:
        id = 0
        while id == 0 or id in self.clients:
            id = random.randint(1, 0xFFFFFFFF - 1)
            if id not in self.clients:
                return id
            
    def rand(self) -> int:
        # Segue o padrão rand() do MSVCRT
        self.rand_seed = (self.rand_seed * 214013 + 2531011) & 0xFFFFFFFF
        return (self.rand_seed >> 16) & 0x7FFF
    
    async def close(self):
        clients = list(self.clients.values())
        await asyncio.gather(*(client.close() for client in clients), return_exceptions=False)
