from __future__ import annotations
import time
import socket
import asyncio
from typing import TYPE_CHECKING
from asyncio import Task, CancelledError
from dependency_injector.providers import Configuration
from gunbound.broker.gameserver import GameServer
if TYPE_CHECKING:
    from gunbound.repository import ServerRepository

class MonitorManager:
    def __init__(self, config: Configuration, server_repository: 'ServerRepository'):
        self.config = config
        self.server_repository = server_repository
        self.servers = [GameServer(index, gameserver) for index, gameserver in enumerate(config['gameservers'])] if config['gameservers'] else []
        self.task: Task = None

    def find(self, index) -> GameServer | None:
        for server in self.servers:
            if server.index == index:
                return server
        return None

    def all(self) -> list[GameServer]:
        return self.servers

    async def check_status(self, timeout=1.0):
        was_online = [server.is_online for server in self.servers]
        tasks = [server.check_status(timeout) for server in self.servers]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # GS caiu: libera os usuários dele já, para poderem entrar em outro GS sem esperar este voltar
        for server, before in zip(self.servers, was_online):
            if before and not server.is_online:
                print(f"[Monitor] GameServer {server.name} ({server.host}:{server.port}) caiu; limpando CurrentUser")
                await self.server_repository.delete_all_users(server.host, server.port)

        await self.server_repository.insert_user_count(
            self.config['broker']['product_version'],
            int.from_bytes(socket.inet_aton(self.config['broker']['host']), 'little'),
            self.config['broker']['port'],
            sum(results)
        )

    async def start(self, interval=10):
        async def loop():
            while True:
                start_time = time.time()
                
                try:
                    await self.check_status()
                except CancelledError:
                    break
                finally:
                    elapsed_time = time.time() - start_time
                    sleep_time = max(0, interval - elapsed_time)
                    await asyncio.sleep(sleep_time)
        
        self.task = asyncio.create_task(loop())

    async def stop(self):
        self.task.cancel()
        try:
            await self.task
        except CancelledError:
            pass

    def is_running(self):
        return self.task and not self.task.done()