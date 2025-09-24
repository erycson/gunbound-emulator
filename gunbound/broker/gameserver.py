
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
        self.version = config['version']
        self.event = config['event']
        self.name = config['name']
        self.description = config['description']
        self.host = config['host']
        self.port = config['port']
        self.authority_min = config['authority']['min']
        self.authority_max = config['authority']['max']
        
        if (len(self.name.encode('latin-1')) > 32):
            raise ValueError(f"Nome do servidor muito longo (máx 32 bytes em latin-1): {self.name} ({len(self.name.encode('latin-1'))} bytes)")
        if (len(self.description.encode('latin-1')) > 64):
            raise ValueError(f"Descrição do servidor muito longa (máx 64 bytes em latin-1): {self.description} ({len(self.description.encode('latin-1'))} bytes)")

        # Status tracking
        self.is_online = False
        self.last_check = 0
        
        # Dados recebidos pelo GameServer
        self.users_max = 0
        self.desconhecido_a = None
        self.users_online = 0
        self.desconhecido_b = None
        self.grade_min = 0
        self.desconhecido_c = None
        self.grade_max = 0
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
        00 00 -> desconhecido_a (?)
        00 00 -> UsersOnline
        00 00 -> desconhecido_b (?)
        00 00 -> UsersMax
        00 00 -> LevelMin (Grande possibilidade ser só um Byte)
        00 00 -> desconhecido_c (?)
        00 00 -> LevelMax (Grande possibilidade ser só um Byte)
        00 -> Avatar ativo
    """
    async def check_status(self, timeout=1.0) -> int:
        transport = None

        try:
            transport, protocol = await asyncio.wait_for(
                asyncio.get_event_loop().create_datagram_endpoint(
                    lambda: UDPFutureProtocol(),
                    remote_addr=(self.host, self.port)
                ),
                timeout=timeout
            )
            
            pack = struct.pack("<BBHI", 0x08, 0x00, 0xF000, self.index)
            transport.sendto(pack)
            
            response_data = await asyncio.wait_for(
                protocol.response_future,
                timeout=timeout
            )
            
            transport.close()
            
            reader = BinaryReader(response_data)
            length = reader.read_uint16()
            if length != 23 or length != reader.size():
                self.is_online = False
                self.last_check = time.time()
                return 0

            cmd = reader.read_int16()
            index = reader.read_uint32()
            # Acredito que dê pra usar esse index pra validar se a resposta é do server certo
            # ou uma validação interna pra que alguem não falsifique a resposta
            if cmd != 0xF000 or index != self.index:
                self.is_online = False
                self.last_check = time.time()
                return 0

            # O que falta descobrir, é como é enviado a informação dizendo que o serveridor tem muita ou pouca gente
            # Se os itens afetam o jogo
            self.desconhecido_a = reader.read_uint16()
            self.users_online = reader.read_uint16() # Não tem certeza
            self.desconhecido_b = reader.read_uint16()
            self.users_max = reader.read_uint16() # RecommendedMan
            self.grade_min = reader.read_int16() # GradeLimitFirst
            self.desconhecido_c = reader.read_uint16()
            self.grade_max = reader.read_int16() # GradeLimitLast
            self.avatar_enabled = reader.read_uint8() == 1

            self.is_online = True
            self.last_check = time.time()

            return self.users_online
        except Exception as e:
            self.is_online = False
            self.last_check = time.time()
            return 0
        finally:
            if transport is not None:
                transport.close()
