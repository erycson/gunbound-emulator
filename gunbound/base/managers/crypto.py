from Crypto.Cipher import AES
from gunbound.util.sha1 import SHA1WithoutROTL

class CryptoManager:
    _instance = None

    def __init__(self, key):
        self.key = bytes.fromhex(key)
        if len(self.key) != 16:
            raise ValueError("A chave de criptografia deve ter 16 bytes (128 bits)")
        
        self.block_size = 16  # 128 bits
        self.key_size = 128
        self.padding = None

    @classmethod
    def initialize(cls, config):
        if cls._instance is not None:
            raise RuntimeError("CryptoManager já inicializado!")

        cls._instance = cls(config)
        return cls._instance
    
    @classmethod
    def get(cls):
        if cls._instance is None:
            raise RuntimeError("CryptoManager não inicializado!")
        return cls._instance

    @classmethod
    def encrypt(cls, plain_text: bytes, key: bytes = None) -> bytes:
        if key is None:
            key = cls.get().key
        return AES.new(key, AES.MODE_ECB).encrypt(plain_text)

    @classmethod
    def decrypt(cls, cipher_text: bytes, key: bytes = None) -> bytes:
        if key is None:
            key = cls.get().key
        return AES.new(key, AES.MODE_ECB).decrypt(cipher_text)

    @classmethod
    def decrypt_custom(cls, data: bytes, key: bytes) -> bytes:
        dec = cls.decrypt(data, key)
        # junta [4:16] de cada bloco
        buf = bytearray()
        for i in range(0, len(dec), 16):
            buf += dec[i + 4 : i + 16]
        return bytes(buf)

    @classmethod
    def derive_key(cls, username: str, password: str, session_id: bytes) -> bytes:
        data = username.encode('latin-1') + password.encode('latin-1') + session_id
        return SHA1WithoutROTL().update(data).digest()[:16]
    