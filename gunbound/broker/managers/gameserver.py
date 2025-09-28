import time
import asyncio
from asyncio import Task, CancelledError
from gunbound.broker.gameserver import GameServer
from gunbound.base.managers import DatabaseManager, ConfigManager

class GameServerManager:
    _instance = None
    
    def __init__(self, configs=[]):
        self.servers = [GameServer(index, config) for index, config in enumerate(configs)] if configs else []
        self.db = DatabaseManager.get()
        self.config = ConfigManager.get()
        self.task: Task = None

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
        print(results)
        
        await self.db.execute(
            "INSERT INTO UserCount (SerialNo, ServerIp, ServerPort, Time, UserCount) VALUES (:no, INET_ATON(:ip), :port, NOW(), :total)",
            {
                'no': self.config['broker']['version'],
                'ip': self.config['broker']['host'],
                'port': self.config['broker']['port'],
                'total': sum(results)
            }
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