# lib/broker/strategy/login_strategy.py
from gunbound.broker.protocol.login import LoginResp
from gunbound.util.sha1 import SHA1WithoutROTL
from gunbound.util.binary_buffer import BinaryReader
from gunbound.broker.managers import ConfigManager, DatabaseManager
from Crypto.Cipher import AES

class LoginStrategy:
    """Interface base para estratégias de login."""
    def process(self, conn, buf):
        raise NotImplementedError

"""Implementação para o cliente GBS WC v440"""
class GBWC_v440_LoginStrategy(LoginStrategy):
    def __init__(self):
        config = ConfigManager.get()
        self.key = bytes.fromhex(config['crypto']['aes_key'])
        self.db = DatabaseManager.get()

    async def process(self, conn, buf: BinaryReader):
        self.buf = buf
        block_a = buf.read_bytes(32)
        block_b = buf.read_bytes(32)

        if (len(block_a) != 32 or len(block_b) != 32):
            print(f"[LoginStrategy] Blocos de dados inválidos. A {len(block_a)}, B {len(block_b)}")
            return

        username_bytes = self.decrypt(block_a[:16])
        session_bytes = self.decrypt(block_a[16:])[:4]

        username = self.c_str(username_bytes)
        session_id = int.from_bytes(session_bytes, "little", signed=True)

        user = await self.find_user(username)
        if not user:
            await conn.on_send(LoginResp.wrong_credentials())
            return

        key_derived = self.derive_key(username_bytes, user.Password, session_bytes)
        password = self.c_str(self.decrypt_custom(block_b, key_derived))

        if user.Password != password:
            await conn.on_send(LoginResp.wrong_credentials())
            return
        
        await conn.on_send(LoginResp.success())

    async def find_user(self, username: str):
        return await self.db.fetch_one(
            'SELECT Authority, UNIX_TIMESTAMP(RestrictTime) AS RestrictTime, Password, Nickname FROM User WHERE User = :user',
            {'user': username}
        )
    
    def c_str(self, b: bytes) -> str:
        """Corta no primeiro 0x00 e decodifica ASCII sem estourar."""
        i = b.find(b"\x00")
        if i != -1:
            b = b[:i]
        return b.decode("ascii", errors="ignore")

    def derive_key(self, username: bytes, password: str, sessionID: bytes) -> bytes:
        """username4 + password4 (ASCII) + session_le4  -> 16B (H0..H3 LE)."""
        m = username.split(b"\x00", 1)[0] + password.encode("ascii") + sessionID
        return SHA1WithoutROTL().update(m).digest()[:16]
    
    def decrypt(self, data: bytes, key: bytes = None) -> bytes:
        if key is None:
            key = self.key
        return AES.new(key, AES.MODE_ECB).decrypt(data)

    def decrypt_custom(self, data: bytes, key: bytes):
        dec = self.decrypt(data, key)
        # junta [4:16] de cada bloco
        buf = bytearray()
        for i in range(0, len(dec), 16):
            buf += dec[i + 4 : i + 16]
        return bytes(buf)