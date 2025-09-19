# -*- coding: utf-8 -*-
# Python 3.7

import struct
from gunbound.util.sha1 import SHA1WithoutROTL
from Crypto.Cipher import AES

key = bytes.fromhex("A92753041BFCACE65B2338346846038C")   # chave fixa (p/ Bloco A)
original_password   = "admin"

def c_str(b: bytes) -> str:
    """Corta no primeiro 0x00 e decodifica ASCII sem estourar."""
    i = b.find(b"\x00")
    if i != -1:
        b = b[:i]
    return b.decode("ascii", errors="ignore")

def decrypt(data: bytes, key: bytes) -> bytes:
    return AES.new(key, AES.MODE_ECB).decrypt(data)

def derive_password_key(username: bytes, password: str, sessionID: bytes) -> bytes:
    """username4 + password4 (ASCII) + session_le4  -> 16B (H0..H3 LE)."""
    m = username.split(b"\x00", 1)[0] + password.encode("ascii") + sessionID
    return SHA1WithoutROTL().update(m).digest()[:16]

"""
Decripta em ECB e, de cada bloco de 16B, usa só os últimos 12B (descarta 4B).
Retorna a C-string (ASCII).
"""
def decrypt_custom(data: bytes, key: bytes):
    dec = decrypt(data, key)
    # junta [4:16] de cada bloco
    buf = bytearray()
    for i in range(0, len(dec), 16):
        buf += dec[i + 4 : i + 16]
    return bytes(buf)

with open("data.bin", "rb") as f:
    binaryPacket = f.read()

checksum, message_type = struct.unpack("<hH", binaryPacket[0:4])
block_a = binaryPacket[4:36]
block_b = binaryPacket[36:68]

# Bloco A com chave fixa
username_raw = decrypt(block_a[:16], key)
session = decrypt(block_a[16:], key)[:4]

# Username para exibir
username = c_str(username_raw)
session_id = int.from_bytes(session, "little", signed=True)
key_derived = derive_password_key(username_raw, original_password, session)
password = c_str(decrypt_custom(block_b, key_derived))

print("\nUsuário:", username)
print("Senha (C-STR):", password)
print("ID da Sessão: {}".format(session_id))
print("Tipo de Mensagem: 0x{:X}".format(message_type))
print("Checksum:", checksum)
