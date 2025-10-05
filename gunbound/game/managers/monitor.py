import time
import socket
import asyncio
from asyncio import CancelledError, Task
from gunbound.game.managers import ClientManager
from gunbound.game.protocol import Feature
from gunbound.game_server import GameServer
from gunbound.repository import ServerRepository
from gunbound.util import dump, BinaryReader, BinaryWriter, UDPFutureProtocol

class MonitorManager:
    _instance = None
    
    def __init__(self, game: GameServer, config):
        self.game = game
        self.config = config
        self.task_broker: Task = None
        self.task_user_count: Task = None
        self.transport = None
        self.manager = ClientManager.get_instance()
        self.server_repository: ServerRepository = ServerRepository()

    @classmethod
    def initialize(cls, game: GameServer, config):
        if cls._instance is not None:
            raise RuntimeError("GameServerManager já inicializado!")

        cls._instance = cls(game, config)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError("MonitorManager não inicializado!")
        return cls._instance
    
    async def start(self):
        self.task_broker = asyncio.create_task(self.udp_listener())
        self.task_user_count = asyncio.create_task(self.user_count_monitor())

    async def udp_listener(self):
        transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
            lambda: UDPFutureProtocol(),
            local_addr=(self.config['host'], self.config['port'])
        )

        while True:
            try:
                response, addr = await protocol.response_future

                reader = BinaryReader(response)
                print(f"UDP-RECV [FROM={addr[0]}:{addr[1]} Accept=1]: {reader.to_hex()}")

                if reader.size() == 4:
                    await self.udp_proc_initial_udp_recv(transport, addr, reader)
                    continue

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
                self.manager.size()
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
        from gunbound.game.managers import RoomManager

        index = reader.read_uint32()
        if index != self.game.index:
            return

        client_manager = ClientManager.get_instance()   
        room_manager = RoomManager.get_instance()

        writer = BinaryWriter()
        writer.write_uint16(23)                         # Size
        writer.write_uint16(0xF001)                     # Command
        writer.write_uint32(self.game.index)            # ServerIndex
        writer.write_uint16(room_manager.size())        # Rooms
        writer.write_uint16(client_manager.size())      # UsersOnline
        writer.write_uint16(self.config['users_max'])   # UsersMax
        writer.write_int16(self.config['grade_max'])    # LevelMin (pode ser q seja só 1 byte)
        writer.write_uint16(0)                          # Desconhecido
        writer.write_int16(self.config['grade_min'])    # LevelMax (pode ser q seja só 1 byte)
        writer.write_uint16(0)                          # Desconhecido
        writer.write_uint8(1 if self.game.features & Feature.AVATAR_ENABLED else 0) # Avatar Enabled

        transport.sendto(writer.getvalue(), addr)

    async def udp_proc_initial_udp_recv(self, transport: asyncio.DatagramTransport, addr, reader: BinaryReader):
        """
        Função que basicamente verifica se o cliente possui o mesmo valor da sequencia.
        Ainda não sei o motivo dessa verificação, mas presumo que é para testar a conexão UDP com o GameServer.
        """
        sequence = reader.read_uint32()

        # Verifica se o valor bate com o atual
        async with self.manager.lock:
            if sequence != self.manager.rand.current_value:
                return
        
        # Uso o BinaryWriter apenas para padronizar o tratamento de dados
        writer = BinaryWriter()
        writer.write_uint32(sequence)

        transport.sendto(writer.getvalue(), addr)