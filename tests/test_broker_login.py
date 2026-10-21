"""0x1010 do broker: senha pura (cliente direto) ou md5[12:32] (NyxLauncher), mesma regra em todas as versões.
python -m unittest tests.test_broker_login"""
import hashlib
import unittest
from gunbound.base.managers import CryptoManager
from gunbound.broker.protocol.login import LoginRecv, LoginResp
from gunbound.util import BinaryReader

CRYPTO = CryptoManager('00' * 16)
SESSION = b'\x01\x02\x03\x04'


class Db:
    async def fetch_one(self, sql, params):
        return {'Password': 'abc'} if params['user'] == 'jogador' else None


class Conn:
    def __init__(self):
        self.sent, self.logged_in = [], False

    async def on_send(self, pkt):
        self.sent.append(pkt.buf.getvalue())


def packet(user, secret):
    """Bloco A: usuário e sessão com a chave do broker; bloco B: senha[20] + versão, 12 bytes úteis por bloco."""
    field = secret.encode('latin-1').ljust(24, b'\x00')
    key = CRYPTO.derive_key(user, secret, SESSION)
    block_b = b''.join(CRYPTO.encrypt(b'\x00' * 4 + field[i:i + 12], key) for i in (0, 12))
    return CRYPTO.encrypt(user.encode().ljust(16, b'\x00')) + CRYPTO.encrypt(SESSION.ljust(16, b'\x00')) + block_b


class BrokerLoginTest(unittest.IsolatedAsyncioTestCase):
    async def login(self, user, secret):
        conn = Conn()
        await LoginRecv(conn, BinaryReader(packet(user, secret)), db=Db(), crypto_manager=CRYPTO).process()
        return conn

    async def test_plain_and_md5_succeed(self):
        for secret in ('abc', hashlib.md5(b'abc').hexdigest()[12:32]):
            conn = await self.login('jogador', secret)
            self.assertEqual((conn.sent, conn.logged_in), ([LoginResp.success().buf.getvalue()], True))

    async def test_wrong_password_and_unknown_user(self):
        for user, secret in (('jogador', 'errada'), ('ninguem', 'abc')):
            conn = await self.login(user, secret)
            self.assertEqual((conn.sent, conn.logged_in), ([LoginResp.wrong_credentials().buf.getvalue()], False))


if __name__ == '__main__':
    unittest.main()
