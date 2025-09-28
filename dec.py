# -*- coding: utf-8 -*-
# Python 3.7

from gunbound.util import dump
from gunbound.util.binary_buffer import BinaryReader
from gunbound.base.managers import ConfigManager, CryptoManager

data = bytes.fromhex("5E107D834310708DBBB2E59E27380D941A14708ED2F6689224748F4165F3E1220E526599281C4854C4FB82F4AF31FEF43C2E0FEBDC180172B117BCBE6812D1C7743ABAFD4D75F4B2C311E96108F3B42E")   # chave fixa (p/ Bloco A)
buf = BinaryReader(data)

config = ConfigManager.initialize("config.yml")
crypto = CryptoManager.initialize(config['crypto']['game_key'])

username = crypto.decrypt(buf.read_bytes(16))
dump(username)
signature = crypto.decrypt(buf.read_bytes(16))
dump(signature)

session_bytes = signature[0:4]

user_key = crypto.derive_key('admin', '1234', session_bytes)
block_1 = crypto.decrypt(buf.read_bytes(16), user_key)
dump(block_1)
block_2 = crypto.decrypt(buf.read_bytes(16), user_key)
dump(block_2)
block_3 = crypto.decrypt(buf.read_bytes(16), user_key)
dump(block_3)