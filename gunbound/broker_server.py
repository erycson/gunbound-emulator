from __future__ import annotations
import socket
import asyncio
from typing import TYPE_CHECKING
from asyncio import Task, CancelledError, StreamReader, StreamWriter
from dependency_injector.providers import Configuration
from gunbound.broker.client import ClientConnection
if TYPE_CHECKING:
    from gunbound.repository import ServerRepository

class BrokerServer:
    def __init__(self, config: Configuration, server_repository: 'ServerRepository'):
        self.id = id(self) & 0xFFFFFFFF
        self.config = config
        self.task: Task = None
        self.connections = []
        self.servers = []
        self.server_repository = server_repository

    async def handler(self, reader: StreamReader, writer: StreamWriter, th: bool = False):
        conn = ClientConnection(self, reader, writer)
        conn.th = th
        conn.task = asyncio.create_task(conn.handler())
        self.connections.append(conn)
    
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
            for connection in list(self.connections):  # close() remove da lista
                await connection.close()
            await self.task
        except CancelledError:
            pass

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
        print(f'BrokerServer iniciado')
        th_port = self.config.get('th_port')
        if th_port:  # o TH manda o mesmo 0x1100 mas lê o 0x1102 com outro layout: só dá para separar pela porta
            th = await asyncio.start_server(lambda r, w: self.handler(r, w, th=True), self.config['host'], th_port)
            print(f'BrokerServer TH iniciado na porta {th_port}')
            await th.start_serving()

        async with server:
            await server.serve_forever()

    def remove(self, connection: ClientConnection):
        if connection in self.connections:
            self.connections.remove(connection)