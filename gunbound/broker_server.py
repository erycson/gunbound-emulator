import asyncio
from gunbound.broker.client import ClientConnection

class BrokerServer:
    def __init__(self, config, crypto):
        self.host = config['host']
        self.port = config['port']
        self.crypto = crypto
        self.server = None
        self.connections = []

    async def handler(self, reader, writer):
        connection = ClientConnection(reader, writer, self.crypto)
        self.connections.append(connection)
        asyncio.create_task(connection.handler())

    async def start(self):
        self.server = await asyncio.start_server(
            self.handler,
            self.host,
            self.port
        )
        print(f'Servidor iniciado')

        async with self.server:
            await self.server.serve_forever()
