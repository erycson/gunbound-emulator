from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.broker.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader

@inject
@BasePackageFactory.register(ClientPacket.CLI_LOGIN.value)
class LoginRecv(BasePackageRecv):
    def __init__(self, conn, buf: BinaryReader, login_strategy = Provide['login_strategy']):
        self.conn = conn
        self.buf = buf
        self.login_strategy = login_strategy

    async def process(self):
        # Delegar para a estratégia selecionada
        await self.login_strategy.process(self.conn, self.buf)

    def log_command(self, conn):
        cmd = ClientPacket.CLI_LOGIN.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.broker.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class LoginResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    """
    00 00 -> RTC (SRV_OK)
    """
    @classmethod
    def success(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(ServerCode.SRV_OK)
        return cls(buf)
    
    """
    11 00 -> RTC (SRV_ERR_WRONG_CREDENTIALS)
    """
    @classmethod
    def wrong_credentials(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(ServerCode.SRV_ERR_WRONG_CREDENTIALS)
        return cls(buf)

    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        code = reader.read_uint16(pos=6)
        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={code:04X}]")