from Crypto.Cipher import AES

class AESCipher:
    def __init__(self, config):
        self.key = bytes.fromhex(config['aes_key'])
        if len(self.key) != 16:
            raise ValueError("A chave de criptografia deve ter 16 bytes (128 bits)")
        
        self.mode = AES.MODE_ECB
        self.block_size = 16  # 128 bits
        self.key_size = 128
        self.padding = None

    def encrypt_block(self, plain_text: bytes) -> bytes:
        if len(plain_text) % self.block_size != 0:
            raise ValueError("O comprimento do plain_text deve ser um múltiplo de 16 (sem padding)")
        cipher = AES.new(self.key, self.mode)
        return cipher.encrypt(plain_text)

    def decrypt_block(self, cipher_text: bytes) -> bytes:
        if len(cipher_text) % self.block_size != 0:
            raise ValueError("O comprimento do cipher_text deve ser um múltiplo de 16 (sem padding)")
        cipher = AES.new(self.key, self.mode)
        return cipher.decrypt(cipher_text)
