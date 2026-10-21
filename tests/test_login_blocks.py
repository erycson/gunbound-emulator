"""0x1010: senha em 20 bytes (block_1[4:16] + block_2[4:12]) e versão sempre em block_2[12:16] (RE dos clientes + logs).
python -m unittest tests.test_login_blocks"""
import hashlib
import struct
import unittest
from gunbound.base.managers import CryptoManager
from gunbound.game.protocol.login import check_password, login_limit

CRYPTO = CryptoManager('00' * 16)
SESSION = b'\x01\x02\x03\x04'


def blocks(user, secret, version):
    """Monta block_1/block_2 como o cliente: prefixo 4 + 12 bytes de dados por bloco."""
    field = secret.encode('latin-1').ljust(20, b'\x00')
    key = CRYPTO.derive_key(user, secret, SESSION)
    b1 = b'\x00' * 4 + field[:12]
    b2 = b'\x00' * 4 + field[12:20] + struct.pack('<I', version)
    return CRYPTO.encrypt(b1, key), CRYPTO.encrypt(b2, key)


class LoginBlocksTest(unittest.TestCase):
    def version(self, checked):
        return struct.unpack_from('<I', checked[1], 12)[0]

    def test_long_plain_password_v440(self):
        pw = 'senhalonga1234567'  # 17 caracteres: antes só os 8 primeiros eram comparados
        checked = check_password(CRYPTO, 'jogador', pw, SESSION, *blocks('jogador', pw, 440))
        self.assertEqual(self.version(checked), 440)

    def test_md5_path_v584(self):
        md5 = hashlib.md5(b'abc').hexdigest()[12:32]
        checked = check_password(CRYPTO, 'jogador', 'abc', SESSION, *blocks('jogador', md5, 4))
        self.assertEqual(self.version(checked), 4)
        self.assertEqual(checked[2], md5)  # a chave da sessão sai dessa senha, não da pura

    def test_wrong_password(self):
        self.assertIsNone(check_password(CRYPTO, 'jogador', 'certa', SESSION, *blocks('jogador', 'errada', 440)))


class LoginLimitTest(unittest.TestCase):  # S3: 0x1012 só com RTC (original 2006 0x42d790 / 2007 0x433cc2)
    def test_rules(self):
        cfg = {'grade_min': 19, 'grade_max': 10, 'guild_limit': 0, 'allowed_guild': []}
        game = {'TotalGrade': 5, 'Guild': ''}
        self.assertEqual(login_limit(game, 0, cfg), 0x5001)
        self.assertIsNone(login_limit(game, 98, cfg))  # Authority >= 98 passa
        cfg['grade_max'] = -4
        self.assertIsNone(login_limit(game, 0, cfg))
        self.assertEqual(login_limit(game, 0, {**cfg, 'guild_limit': 1}), 0x5011)
        self.assertEqual(login_limit({**game, 'Guild': 'abc'}, 0, {**cfg, 'guild_limit': 2}), 0x5012)
        self.assertEqual(login_limit({**game, 'Guild': 'abc'}, 0, {**cfg, 'allowed_guild': ['xyz']}), 0x5013)
        self.assertIsNone(login_limit({**game, 'Guild': 'xyz'}, 0, {**cfg, 'allowed_guild': ['xyz']}))
