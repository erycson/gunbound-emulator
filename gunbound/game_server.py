import asyncio
from asyncio import StreamReader, StreamWriter
from gunbound.game.client import ClientConnection
from gunbound.game.managers.client import ClientManager

class GameServer:
    def __init__(self, index, config):
        self.id = id(self)
        self.index = index
        self.host = config['host']
        self.port = config['port']
        self.server = None
        self.clients = ClientManager.get()
        self.features = self.calc_features(config)

    async def handler(self, reader: StreamReader, writer: StreamWriter):
        client = ClientConnection(self, reader, writer)
        client.task = asyncio.create_task(client.handler())
        self.clients.add(client)

    async def start(self):
        self.server = await asyncio.start_server(
            self.handler,
            self.host,
            self.port
        )
        print(f'GameServer iniciado')

        async with self.server:
            await self.server.serve_forever()

    def calc_features(self, config) -> int:
        features: int = 0
        for feature in config.get('features', []):
            features |= feature
        return features
    
    def remove_connection(self, client: ClientConnection):
        self.clients.remove(client)