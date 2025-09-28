import asyncio
from asyncio import Task, CancelledError, StreamReader, StreamWriter
from gunbound.game.managers.client import ClientManager

class GameServer:
    def __init__(self, index, config):
        self.id = id(self) & 0xFFFFFFFF
        self.index = index
        self.host = config['host']
        self.port = config['port']
        self.version_min = config['version_min']
        self.version_max = config['version_max']
        self.product_version = config['product_version']
        self.task: Task = None
        self.clients = ClientManager.get()
        self.features = self.calc_features(config)

    async def handler(self, reader: StreamReader, writer: StreamWriter):
        await self.clients.add(self, reader, writer)

    async def start(self):
        async def loop():
            server = await asyncio.start_server(
                self.handler,
                self.host,
                self.port
            )
            print(f'GameServer iniciado em {self.host}:{self.port} (features={self.features:04X})')

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
    