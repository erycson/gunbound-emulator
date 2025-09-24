from gunbound.game.client import ClientConnection
from gunbound.game.protocol.enums import ClientPacket, ServerPacket
from gunbound.base.managers import CryptoManager
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader

@BasePackageFactory.register(ClientPacket.CLI_GET_SESSION_ID.value)
class LoginRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn: ClientConnection, buf: BinaryReader):
        self.conn = conn
        self.buf = buf
        self.crypto: CryptoManager = CryptoManager.get()

    async def process(self):
        print(f"[LoginRecv] Processing login packet...: {self.buf.to_hex()}")
        username = self.buf.read_bytes(22)
        print(f"[LoginRecv] Received crypted username: {username}")
        username = self.crypto.decrypt(username)
        print(f"[LoginRecv] Received decrypted username: {username}")
        # await self.conn.on_send(LoginResp.success(self.conn.id))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_LOGIN.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.broker.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex()}")

class LoginResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    """
    04 D1 00 00 -> SessionId 1233
    """
    @classmethod
    def success(cls, session_id: int):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_SESSION_ID)
        buf.write_uint32(session_id)
        return cls(buf)
    
    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex()}")