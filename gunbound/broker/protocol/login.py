from __future__ import annotations
import hashlib
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.broker.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
if TYPE_CHECKING:
    from gunbound.base.database import Database
    from gunbound.base.managers import CryptoManager


def c_str(b: bytes) -> str:
    """Corta no primeiro 0x00 e decodifica ASCII sem estourar."""
    i = b.find(b"\x00")
    return (b[:i] if i != -1 else b).decode("ascii", errors="ignore")


@BasePackageFactory.register(ClientPacket.CLI_LOGIN.value)
@inject
class LoginRecv(BasePackageRecv):
    """Login no broker, igual em todas as versões (TH, WC S1, WC S2): usuário e sessão cifrados com a chave do
    broker no bloco A; senha no bloco B, cifrada com a chave derivada de usuário + senha + sessão."""

    def __init__(self, conn, buf: BinaryReader, db: 'Database' = Provide['database'],
                 crypto_manager: 'CryptoManager' = Provide['crypto']):
        self.conn = conn
        self.buf = buf
        self.db = db
        self.crypto_manager = crypto_manager

    async def process(self):
        block_a = self.buf.read_bytes(32)
        block_b = self.buf.read_bytes(32)
        if len(block_a) != 32 or len(block_b) != 32:
            print(f"[Login] Blocos de dados inválidos. A {len(block_a)}, B {len(block_b)}")
            return

        username = c_str(self.crypto_manager.decrypt(block_a[:16]))
        session_bytes = self.crypto_manager.decrypt(block_a[16:])[:4]

        user = await self.db.fetch_one('SELECT Password FROM User WHERE User = :user', {'user': username})
        if not user:
            print(f"[Login] Usuário não encontrado: {username}")
            await self.conn.on_send(LoginResp.wrong_credentials())
            return

        # cliente direto manda a senha pura; o NyxLauncher manda md5(senha) em hex, caracteres [12:32]
        for expected in (user['Password'], hashlib.md5(user['Password'].encode('latin-1')).hexdigest()[12:32]):
            key = self.crypto_manager.derive_key(username, expected, session_bytes)
            if c_str(self.crypto_manager.decrypt_custom(block_b, key)[:20]) == expected:  # senha[20] + versão u32
                break
        else:
            print(f"[Login] Senha incorreta para o usuário: {username}")  # nunca logar senha
            await self.conn.on_send(LoginResp.wrong_credentials())
            return

        self.conn.logged_in = True
        await self.conn.on_send(LoginResp.success())

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