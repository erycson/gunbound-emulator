
import asyncio
import struct
import time
from enum import Enum
from gunbound.util.dump import dump
from gunbound.util.binary_buffer import BinaryReader
from gunbound.util.udp_protocol import UDPFutureProtocol

class GameServer:
    def __init__(self, index, config):
        self.index = index
        self.host = config['host']
        self.port = config['port']
        self.name = config['name']
        self.description = config['description']
        self.event = config['event']
        
        if (len(self.name.encode('latin-1')) > 32):
            raise ValueError(f"Nome do servidor muito longo (máx 32 bytes em latin-1): {self.name} ({len(self.name.encode('latin-1'))} bytes)")
        if (len(self.description.encode('latin-1')) > 64):
            raise ValueError(f"Descrição do servidor muito longa (máx 64 bytes em latin-1): {self.description} ({len(self.description.encode('latin-1'))} bytes)")

        # Status tracking
        self.is_online = False
        self.last_check: float = 0
        
        # Dados recebidos pelo GameServer
        self.users_online: int = 0
        self.users_max: int = 0
        self.grade_min: int = 0
        self.grade_max: int = 0
        self.avatar_enabled: int = 0

    """
    SEND 08 00 00 F0 00 00 00 00
        08 00 -> PacketSize)
        F0 00 -> Command, 0xF000 = UDP_STATUS_REQ
        00 00 00 00 -> ServerIndex
    RECV 17 00 01 F0 00 00 00 00 00 00 00 00 B8 0B FC FF FF FF 13 00 00 00 00
        17 00 -> PacketSize
        F0 00 -> Comand, 0xF000 = UDP_STATUS_RESP
        00 00 00 00 -> ServerIndex
        00 00 -> 
        00 00 -> UsersOnline
        00 00 -> UsersMax
        00 00 -> LevelMin (Grande possibilidade ser só um Byte)
        00 00 ->
        00 00 -> LevelMax (Grande possibilidade ser só um Byte)
        00 00 -> 
        00 -> Avatar ativo
    """
    async def check_status(self, timeout: float = 2.0) -> int:
        transport: asyncio.DatagramTransport | None = None
        self.last_check = time.time()

        try:
            async with asyncio.timeout(timeout):
                transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
                    lambda: UDPFutureProtocol(),
                    remote_addr=(self.host, self.port)
                )

            timeout = timeout - (time.time() - self.last_check)
            pack = struct.pack("<BBHI", 0x08, 0x00, 0xF000, self.index)
            transport.sendto(pack)

            async with asyncio.timeout(timeout):
                response, addr = await protocol.response_future
            
            reader = BinaryReader(response)
            print(f"UDP-RECV [FROM={addr[0]}:{addr[1]} Accept=1] {reader.to_hex()}")

            length = reader.read_uint16()
            if length != 23 or length != reader.size():
                self.clear_status()
                return 0

            cmd = reader.read_uint16()
            index = reader.read_uint32()
            # Acredito que dê pra usar esse index pra validar se a resposta é do server certo
            # ou uma validação interna pra que alguem não falsifique a resposta
            if cmd != 0xF001 or index != self.index:
                self.clear_status()
                return 0

            # O que falta descobrir, é como é enviado a informação dizendo que o serveridor tem muita ou pouca gente
            # Se os itens afetam o jogo
            reader.read_uint16()
            self.users_online = reader.read_uint16()
            self.users_max = reader.read_uint16() # RecommendedMan
            self.grade_min = reader.read_int16() # GradeLimitFirst
            reader.read_uint16()
            self.grade_max = reader.read_int16() # GradeLimitLast
            reader.read_uint16()
            self.avatar_enabled = reader.read_uint8() == 1

            self.is_online = True

            return self.users_online
        except Exception:
            self.clear_status()
            return 0
        finally:
            if transport is not None and not transport.is_closing():
                transport.close()

    def clear_status(self):
        self.is_online = False
        self.users_max = 0
        self.users_online = 0
        self.grade_min = 0
        self.grade_max = 0
        self.avatar_enabled: int = 0
