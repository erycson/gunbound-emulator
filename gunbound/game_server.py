from __future__ import annotations
import asyncio
from asyncio import Task, CancelledError, StreamReader, StreamWriter
from gunbound.game.client import ClientConnection
from gunbound.game.managers.client import ClientManager

class GameServer:
    def __init__(self, index, config):
        self.id = id(self)
        self.index = index
        self.host = config['host']
        self.port = config['port']
        self.task: Task = None
        self.clients = ClientManager.get()
        self.features = self.calc_features(config)

    async def handler(self, reader: StreamReader, writer: StreamWriter):
        client = ClientConnection(self, reader, writer)
        self.clients.add(client)

    async def start(self):
        async def loop():
            server = await asyncio.start_server(
                self.handler,
                self.host,
                self.port
            )
            print(f'GameServer iniciado')

            async with server:
                await server.serve_forever()
        
        self.task = asyncio.create_task(loop())

    async def stop(self):
        self.task.cancel()
        try:
            await self.clients.close()
            await self.task
        except CancelledError:
            pass

    def calc_features(self, config) -> int:
        features: int = 0
        for feature in config.get('features', []):
            features |= feature
        return features
    
    def remove_connection(self, client: ClientConnection):
        self.clients.remove(client)