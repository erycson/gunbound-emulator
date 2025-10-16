from gunbound.util import dump
from gunbound.base.managers import ConfigManager, CryptoManager

config = ConfigManager.initialize("config.yml")
crypto = CryptoManager.initialize(config['crypto']['game_key'])

# 41, 18467, 6334, 26500, 19169, 15724, 11478, 29358, 26962, 24464
derived_key = crypto.derive_key('test', 'test', (29358).to_bytes(4, 'little'))

data = bytes.fromhex('79 D9 D0 D3 4A 21 5D C9 85 50 A0 6E C8 A4 E6 94')
decrypted = crypto.decrypt(data, derived_key)
dump(decrypted)

