# lib/protocol/login.py

import struct
from gunbound.broker.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.broker.protocol.base import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.broker.managers.config import ConfigManager
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.util.class_loader import instantiate_by_fullname

@BasePackageFactory.register(ClientPacket.CLI_LOGIN.value)
class LoginRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn, buf: BinaryReader):
        self.conn = conn
        self.buf = buf
        self.strategy = self.get_strategy()

    @classmethod
    def get_strategy(cls):
        if cls._strategy is None:
            config = ConfigManager.get()
            strategy_class = config['broker']['strategies']['login']
            cls._strategy = instantiate_by_fullname(strategy_class)
        return cls._strategy

    async def process(self):
        # Delegar para a estratégia selecionada
        await self.strategy.process(self.conn, self.buf)

    def log_command(self, conn):
        cmd = ClientPacket.CLI_LOGIN.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.broker.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex()}")

class LoginResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(ServerCode.SRV_OK)
        return cls(buf)
    
    @classmethod
    def wrong_credentials(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(ServerCode.SRV_ERR_WRONG_CREDENTIALS)
        return cls(buf)

    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        code = reader.read_uint16(pos=6)
        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={code:04X}]")