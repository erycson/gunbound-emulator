from __future__ import annotations
from typing import TYPE_CHECKING
import socket
import asyncio
from asyncio import Task, CancelledError, StreamReader, StreamWriter
from dependency_injector.providers import Configuration
if TYPE_CHECKING:
    from gunbound.repository import ServerRepository
    from gunbound.game.managers import ClientManager, ChannelManager

class GameServer:
    def __init__(
        self,
        index: int,
        config: Configuration,
        channel_manager: 'ChannelManager',
        client_manager: 'ClientManager',
        server_repository: 'ServerRepository',
    ):
        self.id = id(self) & 0xFFFFFFFF
        self.index = index
        self.config = config
        self.task: Task = None
        self.channels = channel_manager
        self.clients = client_manager
        self.server_repository = server_repository
        self.features = self.calc_features(config)

    async def handler(self, reader: StreamReader, writer: StreamWriter):
        await self.clients.add(reader, writer)

    async def start(self):
        self.task = asyncio.create_task(self.tcp_listener())
        await self.server_repository.insert_service_status(
            self.config['product_version'],
            int.from_bytes(socket.inet_aton(self.config['host']), 'little'),
            self.config['port'],
            'S'
        )

    async def stop(self):
        self.task.cancel()
        try:
            await self.clients.close()
            await self.task
        except CancelledError:
            pass

        await self.server_repository.delete_all_users(self.config['host'], self.config['port'])

        await self.server_repository.insert_service_status(
            self.config['product_version'],
            int.from_bytes(socket.inet_aton(self.config['host']), 'little'),
            self.config['port'],
            'T'
        )

    async def tcp_listener(self):
        server = await asyncio.start_server(
            self.handler,
            self.config['host'],
            self.config['port']
        )
        print(f'GameServer iniciado em {self.config["host"]}:{self.config["port"]} (features={self.features:04X})')

        async with server:
            await server.serve_forever()

    def calc_features(self, config) -> int:
        features: int = 0
        for feature in config['features']:
            features |= feature
        return features
    