from __future__ import annotations
import abc
from typing import TYPE_CHECKING
from gunbound.base.database import Database
from gunbound.broker.protocol.login import LoginResp
from gunbound.util import BinaryReader
if TYPE_CHECKING:
    from gunbound.base.managers import CryptoManager
    from gunbound.broker.client import ClientConnection

class LoginStrategy(abc.ABC):
    def __init__(
        self,
        db: Database,
        crypto_manager: 'CryptoManager'
    ):
        self.db = db
        self.crypto_manager = crypto_manager

    @abc.abstractmethod
    async def process(self, conn: 'ClientConnection', buf: BinaryReader):
        pass

class GBWC_v440_LoginStrategy(LoginStrategy):
    """Implementação para o cliente GBS WC v440"""

    async def process(self, conn: 'ClientConnection', buf: BinaryReader):
        self.buf = buf
        block_a = buf.read_bytes(32)
        block_b = buf.read_bytes(32)

        if (len(block_a) != 32 or len(block_b) != 32):
            print(f"[LoginStrategy] Blocos de dados inválidos. A {len(block_a)}, B {len(block_b)}")
            return

        username_bytes = self.crypto_manager.decrypt(block_a[:16])
        session_bytes = self.crypto_manager.decrypt(block_a[16:])[:4]

        username = self.c_str(username_bytes)
        session_id = int.from_bytes(session_bytes, "little", signed=True)

        user = await self.find_user(username)
        if not user:
            print(f"[LoginStrategy] Usuário não encontrado: {username}")
            await conn.on_send(LoginResp.wrong_credentials())
            return

        key_derived = self.crypto_manager.derive_key(username, user['Password'], session_bytes)
        password = self.c_str(self.crypto_manager.decrypt_custom(block_b, key_derived))

        if user['Password'] != password:
            print(f"[LoginStrategy] Senha incorreta para o usuário: '{username}', senha recebida: '{password}', esperada: '{user['Password']}'")
            await conn.on_send(LoginResp.wrong_credentials())
            return
        
        await conn.on_send(LoginResp.success())

    async def find_user(self, username: str):
        return await self.db.fetch_one(
            'SELECT Authority, RestrictTime, Password, Nickname FROM User WHERE User = :user',
            {'user': username}
        )
    
    def c_str(self, b: bytes) -> str:
        """Corta no primeiro 0x00 e decodifica ASCII sem estourar."""
        i = b.find(b"\x00")
        if i != -1:
            b = b[:i]
        return b.decode("ascii", errors="ignore")
