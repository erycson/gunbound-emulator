import time
import socket
import asyncio
from asyncio import CancelledError, Task
from gunbound.game.managers.client import ClientManager
from gunbound.game.protocol.enums import Features
from gunbound.game_server import GameServer
from gunbound.respository import ServerRepository
from gunbound.util import BinaryReader, BinaryWriter, UDPFutureProtocol

class MonitorManager:
    _instance = None
    
    def __init__(self, game: GameServer, config):
        self.game = game
        self.config = config
        self.task_broker: Task = None
        self.task_user_count: Task = None
        self.transport = None
        self.clients = ClientManager.get()
        self.server_repository: ServerRepository = ServerRepository()

    @classmethod
    def initialize(cls, game: GameServer, config):
        if cls._instance is not None:
            raise RuntimeError("GameServerManager já inicializado!")

        cls._instance = cls(game, config)
        return cls._instance

    @classmethod
    def get(cls):
        if cls._instance is None:
            raise RuntimeError("MonitorManager não inicializado!")
        return cls._instance
    
    async def start(self):
        self.task_broker = asyncio.create_task(self.broker_listener())
        self.task_user_count = asyncio.create_task(self.user_count_monitor())

    async def broker_listener(self):
        transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
            lambda: UDPFutureProtocol(),
            local_addr=(self.config['host'], self.config['port'])
        )

        while True:
            try:
                response, addr = await protocol.response_future

                reader = BinaryReader(response)
                print(f"UDP-RECV [FROM={addr[0]}:{addr[1]} Accept=1]: {reader.to_hex()}")

                length = reader.read_uint16()
                if length != reader.size() or reader.size() < 4:
                    continue
                
                match reader.read_uint16():
                    case 0xF000:
                        await self.udp_get_state(transport, addr, reader)
            except CancelledError:
                protocol.response_future.cancel()
                transport.close()
                break
            finally:
                protocol.response_future = asyncio.Future()

    async def user_count_monitor(self):
        interval = self.config['stats_interval']

        await asyncio.sleep(interval)
        while True:
            start_time = time.time()
            
            await self.server_repository.insert_user_count(
                self.config['broker']['version'],
                int.from_bytes(socket.inet_aton(self.config['broker']['host']), 'little'),
                self.config['broker']['port'],
                self.clients.size()
            )

            elapsed_time = time.time() - start_time
            sleep_time = max(0, interval - elapsed_time)
            await asyncio.sleep(sleep_time)


    async def stop(self):
        self.task_broker.cancel()
        self.task_user_count.cancel()

        try:
            await self.task_broker
            await self.task_user_count
        except CancelledError:
            pass

    def is_running(self):
        return self.task_broker and not self.task.done()

    async def udp_get_state(self, transport: asyncio.DatagramTransport, addr, reader: BinaryReader):
        index = reader.read_uint32()
        if index != self.game.index:
            return

        manager = ClientManager.get()   

        writer = BinaryWriter()
        writer.write_uint16(23)  # Size
        writer.write_uint16(0xF001) # Command
        writer.write_uint32(self.game.index) # ServerIndex
        writer.write_bytes([0x00, 0x00])  # Desconhecido
        writer.write_bytes([0x00, 0x00])  # Desconhecido
        writer.write_uint16(manager.size())  # UsersOnline
        writer.write_uint16(self.config['users_max'])  # UsersMax
        writer.write_int16(self.config['grade_min']) # LevelMin (pode ser q seja só 1 byte)
        writer.write_bytes([0x00, 0x00]) # Desconhecido
        writer.write_int16(self.config['grade_max'])  # LevelMax (pode ser q seja só 1 byte)
        writer.write_byte(1 if self.game.features & Features.AVATAR_ENABLED else 0) # Avatar Enabled

        transport.sendto(writer.getvalue(), addr)