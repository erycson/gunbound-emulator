from Crypto.Cipher import AES
from gunbound.util.sha1 import SHA1WithoutROTL

class CryptoManager:
    def __init__(self, key):
        self.key = bytes.fromhex(key)
        if len(self.key) != 16:
            raise ValueError("A chave de criptografia deve ter 16 bytes (128 bits)")
        self.aes = AES.new(self.key, AES.MODE_ECB)

    def encrypt(self, plain_text: bytes, key: bytes = None) -> bytes:
        if key is None:
            key = self.key
        return self.aes.encrypt(plain_text)

    def decrypt(self, cipher_text: bytes, key: bytes = None) -> bytes:
        if key is None:
            key = self.key
        return self.aes.decrypt(cipher_text)

    def decrypt_custom(self, data: bytes, key: bytes) -> bytes:
        dec = self.decrypt(data, key)
        # junta [4:16] de cada bloco
        buf = bytearray()
        for i in range(0, len(dec), 16):
            buf += dec[i + 4 : i + 16]
        return bytes(buf)

    def derive_key(self, username: str, password: str, session_id: bytes) -> bytes:
        data = username.encode('latin-1') + password.encode('latin-1') + session_id
        return SHA1WithoutROTL().update(data).digest()[:16]
    