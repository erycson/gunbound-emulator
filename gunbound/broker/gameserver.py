
import asyncio
import struct
import time
from enum import Enum
from gunbound.util.dump import dump
from gunbound.util.binary_buffer import BinaryReader

class ServerStatus(Enum):
    UNKNOWN = "unknown"
    ONLINE = "online" 
    OFFLINE = "offline"

class StatusProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport = None
        self.response_future = asyncio.Future()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if not self.response_future.done():
            self.response_future.set_result(data)

class GameServer:
    def __init__(self, config):
        self.id = config['id']
        self.version = config['version']
        self.name = config['name']
        self.description = config['description']
        self.host = config['host']
        self.port = config['port']
        self.authority_min = config['authority']['min']
        self.authority_max = config['authority']['max']
        
        # Status tracking
        self.status = ServerStatus.UNKNOWN
        self.last_check = 0
        
        # Server metrics from UDP_STATUS_RESP
        self.metric_u16 = None
        self.users_online = None
        self.metric_b = None
        self.frame = None
        self.latency = None
        self.flag = None

    """
    SEND 08 00 00 F0 00 00 00 00
        PacketSize: 08 00 (8 bytes)
        Command: F0 00 (0xF000 = UDP_STATUS_REQ)
        ServerIndex: 00 00 00 00 (GameServer ID, little-endian)
    RECV 17 00 01 F0 00 00 00 00 00 00 00 00 B8 0B FC FF FF FF 13 00 00 00 00
        PacketSize: 17 00 (23 bytes)
        Command: F0 00 (0xF000 = UDP_STATUS_RESP)
        ServerIndex: 00 00 00 00 (GameServer ID, little-endian)
        Metric1: B8 0B (0x0BB8 = 3000, exemplo)
        UsersOnline: FC FF (0xFFFC = 65532, exemplo)
        Metric3: FF FF (0xFFFF = 65535, exemplo)
        Frame: 13 00 00 00 (0x00000013 = 19, exemplo)
        Latency: 00 00 00 00 (0x00000000 = 0ms, exemplo)
        Flag: 00 (0x00 = Normal, exemplo)
    """
    async def check_status(self, timeout=1.0) -> int:
        transport = None

        try:
            transport, protocol = await asyncio.wait_for(
                asyncio.get_event_loop().create_datagram_endpoint(
                    lambda: StatusProtocol(),
                    remote_addr=(self.host, self.port)
                ),
                timeout=timeout
            )
            
            pack = struct.pack("<BBHI", 0x08, 0x00, 0xF000, self.id)
            transport.sendto(pack)
            
            response_data = await asyncio.wait_for(
                protocol.response_future,
                timeout=timeout
            )
            
            transport.close()
            
            reader = BinaryReader(response_data)
            length = reader.read_uint16()
            cmd = reader.read_int16()
            reader.read_uint32() # server_index
            self.metric_u16 = reader.read_uint16()
            self.users_online = reader.read_uint16()
            self.metric_b = reader.read_uint16()
            self.frame = reader.read_uint32()
            self.latency = reader.read_uint32()
            self.flag = reader.read_uint8()

            print(f"[GameServer:{self.id}] M1: {self.metric_u16:#04x}, Users Online: {self.users_online}, M3: {self.metric_b:#04x}, Frame: {self.frame:#08x}, Latency: {self.latency}ms, Flag: {self.flag}")
            
            self.status = ServerStatus.ONLINE
            self.last_check = time.time()

            return self.users_online
        except Exception as e:
            self.status = ServerStatus.OFFLINE
            self.last_check = time.time()
            return 0
        finally:
            if transport is not None:
                transport.close()

    def is_online(self):
        return self.status == ServerStatus.ONLINE
