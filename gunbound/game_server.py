import socket
import asyncio
from asyncio import Task, CancelledError, StreamReader, StreamWriter
from gunbound.game.managers import ClientManager, ChannelManager
from gunbound.respository import ServerRepository

class GameServer:
    def __init__(self, index, config):
        self.id = id(self) & 0xFFFFFFFF
        self.index = index
        self.host = config['host']
        self.port = config['port']
        self.config = config
        self.task: Task = None
        self.channels: ChannelManager = ChannelManager.get()
        self.clients: ClientManager = ClientManager.get()
        self.features = self.calc_features(config)
        self.server_repository: ServerRepository = ServerRepository()

    async def handler(self, reader: StreamReader, writer: StreamWriter):
        await self.clients.add(self, reader, writer)

    async def start(self):
        self.task = asyncio.create_task(self.tcp_listener())
        await self.server_repository.insert_service_status(
            self.config['product_version'],
            int.from_bytes(socket.inet_aton(self.host), 'little'),
            self.port,
            'S'
        )

    async def stop(self):
        self.task.cancel()
        try:
            await self.clients.close()
            await self.task
        except CancelledError:
            pass

        await self.server_repository.insert_service_status(
            self.config['product_version'],
            int.from_bytes(socket.inet_aton(self.host), 'little'),
            self.port,
            'T'
        )

    async def tcp_listener(self):
        server = await asyncio.start_server(
            self.handler,
            self.host,
            self.port
        )
        print(f'GameServer iniciado em {self.host}:{self.port} (features={self.features:04X})')

        async with server:
            await server.serve_forever()

    def calc_features(self, config) -> int:
        features: int = 0
        for feature in config.get('features', []):
            features |= feature
        return features
    