from __future__ import annotations
import time
import asyncio
from asyncio import StreamReader, StreamWriter
from typing import TYPE_CHECKING
from gunbound.game.client import ClientConnection
from gunbound.util import synchronized, MSVCRTRand
if TYPE_CHECKING:
    from gunbound import GameServer

""""
Gerencia as conexões dos clientes.

Isso foi implementado, pois, diferente do Broker, que possui regras mais simples, o GameServer precisa manter 
uma grande quantidade de regras, e para separar responsabilidades, foi decidido criar esse manager.
"""
class ClientManager:
    _instance = None
    
    def __init__(self):
        self.clients: dict = {}  # id -> ClientConnection
        self.lock = asyncio.Lock()
        self.rand: MSVCRTRand = MSVCRTRand()

    @classmethod
    def initialize(cls):
        if cls._instance is not None:
            raise RuntimeError("ClientManager já inicializado!")

        cls._instance = cls()
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError("ClientManager não inicializado!")
        return cls._instance
    
    def size(self) -> int:
        return len(self.clients)
    
    @synchronized()
    async def add(self, server: 'GameServer', reader: StreamReader, writer: StreamWriter):
        prng_seed = int(time.time() + id(self)) & 0xFFFFFFFF
        client = ClientConnection(server, self, prng_seed, reader, writer)
        client.task = asyncio.create_task(client.handler())
        self.clients[client.id] = client

    @synchronized()
    async def remove(self, client: ClientConnection) -> bool:
        if client.id in self.clients:
            del self.clients[client.id]
            return True
        return False
    
    async def close(self):
        await asyncio.gather(*(conn.close() for conn in self.clients.values()), return_exceptions=False)
