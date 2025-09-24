import asyncio
from gunbound.game.managers.client import ClientManager
from gunbound.game.protocol.enums import Features
from gunbound.game_server import GameServer
from gunbound.util.binary_buffer import BinaryReader, BinaryWriter
from gunbound.util.udp_protocol import UDPFutureProtocol

class MonitorManager:
    _instance = None
    
    def __init__(self, game: GameServer, config):
        self.game = game
        self.config = config
        self.monitor_task = None

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
    
    def start_monitor(self, interval=10):
        if self.monitor_task and not self.monitor_task.done():
            return
            
        async def loop():
            transport, protocol = asyncio.get_event_loop().create_datagram_endpoint(
                lambda: UDPFutureProtocol(),
                remote_addr=(self.config['host'], self.config['port'])
            )

            while True:
                try:
                    response_data = await asyncio.wait_for(protocol.response_future)
                    host, port = transport.get_extra_info('peername')
                    
                    reader = BinaryReader(response_data)

                    length = reader.read_uint16()
                    if length != reader.size() or reader.size() < 4:
                        print(f"UDP-RECV [FROM={host}:{port} Accept=0]")
                        continue

                    print(f"UDP-RECV [FROM={host}:{port} Accept=1]: {reader.to_hex()}")
                    
                    match reader.read_uint16():
                        case 0xF000:
                            self.udp_get_state(transport, reader)
                            break
                finally:
                    transport.close()
        
        self.monitor_task = asyncio.create_task(loop())

    def stop_monitor(self):
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()

    def is_monitor_running(self):
        return self.monitor_task and not self.monitor_task.done()

    async def udp_get_state(self, transport, reader):
        index = reader.read_uint32()
        if index != self.game.index:
            return

        session = ClientManager.get()

        writer = BinaryWriter()
        writer.write_uint16(23)  # Size
        writer.write_uint16(0xF000) # Command
        writer.write_uint32(self.game.index) # ServerIndex
        writer.write_bytes([0x00, 0x00])  # Desconhecido
        writer.write_uint16(session.size())  # UsersOnline
        writer.write_bytes([0x00, 0x00])  # Desconhecido
        writer.write_uint16(self.config['users_max'])  # UsersMax
        writer.write_int16(self.config['grade_min']) # LevelMin (pode ser q seja só 1 byte)
        writer.write_bytes([0x00, 0x00]) # Desconhecido
        writer.write_int16(self.config['grade_max'])  # LevelMax (pode ser q seja só 1 byte)
        writer.write_byte(1 if self.game.features & Features.AVATAR_ENABLED else 0) # Avatar Enabled

        transport.sendto(writer.get_bytes())