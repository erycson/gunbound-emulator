from __future__ import annotations
import time
import asyncio
from asyncio import StreamReader, StreamWriter
from dependency_injector.providers import Factory
from typing import TYPE_CHECKING
from gunbound.util import synchronized, MSVCRTRand
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection
    from gunbound import GameServer

""""
Gerencia as conexões dos clientes.

Isso foi implementado, pois, diferente do Broker, que possui regras mais simples, o GameServer precisa manter 
uma grande quantidade de regras, e para separar responsabilidades, foi decidido criar esse manager.
"""
class ClientManager:
    def __init__(self, client_factory: Factory['ClientConnection']):
        self.client_factory = client_factory
        self.clients: dict[int, ClientConnection] = {}
        self.lock = asyncio.Lock()
        self.rand: MSVCRTRand = MSVCRTRand()

    def size(self) -> int:
        return len(self.clients)
    
    @synchronized()
    async def add(self, reader: StreamReader, writer: StreamWriter):
        prng_seed = int(time.time() + id(self)) & 0xFFFFFFFF
        client = self.client_factory(prng_seed, reader, writer)
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
