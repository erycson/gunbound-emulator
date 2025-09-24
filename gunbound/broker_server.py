import asyncio
from gunbound.broker.client import ClientConnection

class BrokerServer:
    def __init__(self, config):
        self.id = id(self)
        self.host = config['host']
        self.port = config['port']
        self.server = None
        self.connections = []
        self.servers = []

    async def handler(self, reader, writer):
        connection = ClientConnection(self, reader, writer)
        self.connections.append(connection)
        asyncio.create_task(connection.handler())

    async def start(self):
        self.server = await asyncio.start_server(
            self.handler,
            self.host,
            self.port
        )
        print(f'BrokerServer iniciado')

        async with self.server:
            await self.server.serve_forever()

    def remove_connection(self, connection: ClientConnection):
        if connection in self.connections:
            self.connections.remove(connection)