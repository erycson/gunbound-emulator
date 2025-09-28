import asyncio
import random
from gunbound.game.client import ClientConnection

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
    
    async def add(self, server, reader, writer):
        async with self.lock:
            client = ClientConnection(server, self, self.generate_id(), reader, writer)
            client.task = asyncio.create_task(client.handler())
            self.clients[client.id] = client

    async def remove(self, client: ClientConnection) -> bool:
        async with self.lock:
            if client.id in self.clients:
                del self.clients[client.id]
                return True
            return False

    def generate_id(self) -> int:
        id = 0
        while id == 0 or id in self.clients:
            id = random.randint(1, 4294967295)  # Gera int32 positivo (0 a 2^32-1)
        return id
    
    async def close(self):
        clients = list(self.clients.values())
        await asyncio.gather(*(client.close() for client in clients), return_exceptions=False)
