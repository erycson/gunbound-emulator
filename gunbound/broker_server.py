import socket
import asyncio
from asyncio import Task, CancelledError, StreamReader, StreamWriter
from gunbound.broker.client import ClientConnection
from gunbound.respository import ServerRepository

class BrokerServer:
    def __init__(self, config):
        self.id = id(self) & 0xFFFFFFFF
        self.host = config['host']
        self.port = config['port']
        self.task: Task = None
        self.connections = []
        self.servers = []
        self.server_repository: ServerRepository = ServerRepository()

    async def handler(self, reader: StreamReader, writer: StreamWriter):
        conn = ClientConnection(self, reader, writer)
        conn.task = asyncio.create_task(conn.handler())
        self.connections.append(conn)
    
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
            for connection in self.connections:
                await connection.close()
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
        print(f'BrokerServer iniciado')

        async with server:
            await server.serve_forever()

    def remove(self, connection: ClientConnection):
        if connection in self.connections:
            self.connections.remove(connection)