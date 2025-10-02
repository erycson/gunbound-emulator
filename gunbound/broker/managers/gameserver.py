import time
import socket
import asyncio
from asyncio import Task, CancelledError
from gunbound.broker.gameserver import GameServer
from gunbound.base.managers import ConfigManager
from gunbound.respository import ServerRepository

class GameServerManager:
    _instance = None
    
    def __init__(self, configs=[]):
        self.servers = [GameServer(index, config) for index, config in enumerate(configs)] if configs else []
        self.config = ConfigManager.get()
        self.task: Task = None
        self.server_repository: ServerRepository = ServerRepository()

    @classmethod
    def initialize(cls, configs):
        if cls._instance is not None:
            raise RuntimeError("GameServerManager já inicializado!")

        cls._instance = cls(configs)
        return cls._instance

    @classmethod
    def get(cls):
        if cls._instance is None:
            raise RuntimeError("GameServerManager não inicializado!")
        return cls._instance
    
    def find(self, index) -> GameServer | None:
        for server in self.servers:
            if server.index == index:
                return server
        return None

    def all(self) -> list[GameServer]:
        return self.servers

    async def check_status(self, timeout=1.0):
        tasks = [server.check_status(timeout) for server in self.servers]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        await self.server_repository.insert_user_count(
            self.config['broker']['version'],
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