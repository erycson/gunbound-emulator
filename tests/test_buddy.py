"""
BuddyServ: login cifrado como o cliente TH (CBuddy2 0x4e9166), lista, estados, add/remove, túnel e mensagens guardadas.
Servidor real numa porta local temporária; banco = repositório falso em memória.
Uso: python -m unittest tests.test_buddy -v
"""
import asyncio
import hashlib
import struct
import unittest
from gunbound.buddy import server as bs
from gunbound.base.managers.crypto import CryptoManager

USERS = {
    'test': {'Id': 'test', 'Nickname': 'test', 'Password': 'pw1', 'Guild': 'G1', 'TotalGrade': 19},
    'mario': {'Id': 'mario', 'Nickname': 'MarioZ', 'Password': 'pw2', 'Guild': 'GmTeam', 'TotalGrade': 1},
    'luigi': {'Id': 'luigi', 'Nickname': 'Luigi', 'Password': 'pw3', 'Guild': '', 'TotalGrade': 5},
}


class FakeRepo:
    def __init__(self):
        self.buddies = []  # (Id, Category, Buddy)
        self.packets = []  # dicts
        self.serial = 0
        self.not_in_game = set()

    async def game_session_ip(self, user_id):
        return None if user_id in self.not_in_game else bytes([127, 0, 0, 1])

    async def get_user(self, user_id):
        return next((dict(u) for k, u in USERS.items() if k.lower() == user_id.lower()), None)

    async def get_buddies(self, user_id):
        rows = [(c, b) for i, c, b in self.buddies if i == user_id]
        return [{'Buddy': b, 'Category': c, 'Nickname': USERS[b]['Nickname'], 'Guild': USERS[b]['Guild'],
                 'TotalGrade': USERS[b]['TotalGrade']} for c, b in sorted(rows)]

    async def buddy_of(self, user_id):
        return [i for i, _, b in self.buddies if b == user_id]

    async def add(self, user_id, buddy, category):
        self.buddies.append((user_id, category, buddy))
        return True

    async def remove(self, user_id, buddy):
        before = len(self.buddies)
        self.buddies = [x for x in self.buddies if not (x[0] == user_id and x[2] == buddy)]
        return len(self.buddies) < before

    async def set_category(self, user_id, buddies, category):
        self.buddies = [(i, category if i == user_id and b in buddies else c, b) for i, c, b in self.buddies]

    async def rename_category(self, user_id, old, new):
        self.buddies = [(i, new if i == user_id and c == old else c, b) for i, c, b in self.buddies]

    async def search(self, nickname, user_id, offset, count):
        found = [u for u in USERS.values() if (not user_id or u['Id'].startswith(user_id))
                 and (not nickname or u['Nickname'].startswith(nickname))] if (nickname or user_id) else []
        return found[offset:offset + count]

    async def save_packet(self, receiver, sender, code, body):
        self.serial += 1
        self.packets.append({'SerialNo': self.serial, 'Receiver': receiver, 'Sender': sender, 'Code': code,
                             'Body': body, 'Time': None, 'Nickname': USERS[sender]['Nickname']})
        return self.serial

    async def get_packets(self, receiver):
        return [p for p in self.packets if p['Receiver'] == receiver]

    async def delete_packets(self, receiver, serials):
        self.packets = [p for p in self.packets if not (p['Receiver'] == receiver and p['SerialNo'] in serials)]


class Client:
    """Imita o CBuddy2 do TH."""
    crypto = CryptoManager(bs.STATIC_KEY)

    def __init__(self, user_id, password, version=0x19):
        self.user_id, self.password, self.version = user_id, password, version

    async def connect(self, port):
        self.reader, self.writer = await asyncio.open_connection('127.0.0.1', port)

    async def send(self, cmd, body=b''):
        self.writer.write(bs.packet(cmd, body))
        await self.writer.drain()

    async def recv(self):
        size, cmd = struct.unpack('<HH', await asyncio.wait_for(self.reader.readexactly(4), 2))
        return cmd, await self.reader.readexactly(size - 4)

    async def login(self):
        await self.send(bs.SVC_PRECREDENTIAL)
        cmd, body = await self.recv()
        assert cmd == bs.RET_PRECREDENTIAL and len(body) == 4
        assert (await self.recv())[1][:4] == body  # 0x1001 de 8 bytes do v584, que o TH descarta
        self.key = self.crypto.derive_key(self.user_id, self.password, body)
        plain = struct.pack('<I', self.version) + self.password.encode().ljust(20, b'\0')
        plain += bytes([127, 0, 0, 1]) + struct.pack('>H', 5000) + b'\xAA' * 6  # IP local, porta UDP, lixo
        login = self.crypto.encrypt(self.user_id.encode().ljust(16, b'\0'))
        login += self.crypto.encrypt(body + b'\xCC' * 12)
        login += bs.encrypt_blocks(self.crypto, self.key, plain)
        assert len(login) == 0x50
        await self.send(bs.SVC_LOGIN, login)
        return await self.recv()

    async def close(self):
        self.writer.close()


class V584Client(Client):
    """Imita o Buddy2.dll do WC S2 v584: Id 20, nick/guild UTF-16, senha vazia, login de 0xD0."""
    def __init__(self, user_id, nick='', ext=b'\x07\x00\x07\x00' + b'\xFF' * 12):
        super().__init__(user_id, '')
        self.nick, self.ext = nick, ext

    async def login(self):
        await self.send(bs.SVC_PRECREDENTIAL)
        assert len((await self.recv())[1]) == 4  # o do TH: o v584 descarta
        cmd, body = await self.recv()
        assert cmd == bs.RET_PRECREDENTIAL and len(body) == 8
        nonce = body[:4]
        self.key = self.crypto.derive_key(self.user_id, '', nonce)
        uid = uid20(self.user_id)
        plain = struct.pack('<I', 0x1B) + b'\0' * 20 + bytes([127, 0, 0, 1]) + struct.pack('>H', 5000)
        plain += w40(self.nick) + b'\0' * 40 + self.ext
        login = self.crypto.encrypt(uid[:16]) + self.crypto.encrypt(uid[16:] + nonce + b'\xCC' * 8)
        login += bs.encrypt_blocks(self.crypto, self.key, plain)
        assert len(login) == 0xD0
        await self.send(bs.SVC_LOGIN, login)
        return await self.recv()


def uid20(user_id):
    return user_id.encode().ljust(20, b'\0')


def w40(text):
    return text.encode('utf-16-le').ljust(40, b'\0')


class BuddyTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repo = FakeRepo()
        self.buddy = bs.BuddyServer(self.repo)
        self.server = await asyncio.start_server(self.buddy.handle, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.clients = []

    async def asyncTearDown(self):
        for c in self.clients:
            await c.close()
        self.server.close()
        await self.server.wait_closed()

    async def client(self, user_id, password, cls=Client, **kw):
        c = cls(user_id, password, **kw) if cls is Client else cls(user_id, **kw)
        await c.connect(self.port)
        self.clients.append(c)
        return c

    async def test_login_ok_and_list(self):
        self.repo.buddies = [('mario', 'Amigos', 'test'), ('mario', 'Amigos', 'luigi')]
        c = await self.client('mario', 'pw2')
        cmd, body = await c.login()
        self.assertEqual(cmd, bs.RET_LOGIN)
        rtc, token = struct.unpack_from('<HI', body)
        self.assertEqual(rtc, 0)
        self.assertEqual(body[6:12], b'MarioZ')
        self.assertEqual(body[0x12:0x18], b'GmTeam')
        self.assertEqual(struct.unpack_from('<HH', body, 0x1A), (1, 2))
        # 1ª entrada leva a categoria (20 bytes), a 2ª com a mesma categoria leva 1 byte 0
        first = body[0x1E:]
        self.assertEqual(first[0:5], b'luigi')
        self.assertEqual(first[28:34], b'Amigos')
        second = first[28 + 20 + 10:]
        self.assertEqual(second[0:4], b'test')
        self.assertEqual(second[28], 0)
        self.assertEqual(len(second), 28 + 1 + 10)
        cmd, body = await c.recv()  # estado dos amigos: todos offline
        self.assertEqual(cmd, bs.NTF_USER_STATE)
        self.assertEqual(body, struct.pack('<H', 2) + b'luigi'.ljust(16, b'\0') + b'\0' + b'test'.ljust(16, b'\0') + b'\0')

    async def test_md5_password_from_launcher(self):
        md5 = hashlib.md5(b'pw1').hexdigest()[12:32]
        cmd, body = await (await self.client('test', md5)).login()
        self.assertEqual(struct.unpack_from('<H', body)[0], 0)

    async def test_login_errors(self):
        self.assertEqual((await (await self.client('test', 'errada')).login())[1], struct.pack('<H', bs.BAD_PASSWORD))
        self.assertEqual((await (await self.client('ninguem', 'x')).login())[1], struct.pack('<H', bs.NOT_FOUND))
        self.assertEqual((await (await self.client('test', 'pw1', version=601)).login())[1], struct.pack('<H', bs.BAD_VERSION))

    async def test_online_offline_and_add(self):
        self.repo.buddies = [('mario', '', 'test')]
        mario = await self.client('mario', 'pw2')
        await mario.login()
        await mario.recv()  # 0x3FFF: test offline
        test = await self.client('test', 'pw1')
        await test.login()
        cmd, body = await mario.recv()  # test entrou: 0x3FFF com 1 entrada online
        self.assertEqual(cmd, bs.NTF_USER_STATE)
        self.assertEqual(body[2:6], b'test')
        self.assertEqual(body[18], 1)
        self.assertEqual(len(body), 2 + 0x1D)

        # test adiciona mario (unilateral, como o original)
        await test.send(bs.SVC_ADD_BUDDY, b'mario'.ljust(16, b'\0') + b'\0' * 20)
        cmd, body = await test.recv()
        self.assertEqual(cmd, bs.RET_ADD_BUDDY)
        self.assertEqual(struct.unpack_from('<H', body)[0], 0)
        self.assertEqual(body[2:7], b'mario')
        self.assertEqual(body[18:24], b'MarioZ')
        self.assertEqual(len(body), 2 + 38)
        cmd, body = await test.recv()
        self.assertEqual((cmd, body[18]), (bs.NTF_USER_STATE, 1))
        await test.send(bs.SVC_ADD_BUDDY, b'mario'.ljust(16, b'\0') + b'\0' * 20)  # repetido: OK de novo, sem duplicar
        self.assertEqual((await test.recv())[1][:7], struct.pack('<H', 0) + b'mario')
        self.assertEqual((await test.recv())[0], bs.NTF_USER_STATE)
        self.assertEqual(self.repo.buddies.count(('test', '', 'mario')), 1)
        await test.send(bs.SVC_ADD_BUDDY, b'test'.ljust(16, b'\0') + b'\0' * 20)
        self.assertEqual(await test.recv(), (bs.RET_ADD_BUDDY, struct.pack('<H', bs.NOT_FOUND)))

        await test.close()
        cmd, body = await mario.recv()  # test saiu
        self.assertEqual(body, struct.pack('<H', 1) + b'test'.ljust(16, b'\0') + b'\0')

    async def test_accept_both_sides_add(self):
        """Fluxo do cliente: quem aceita manda 0x3000(pedinte) e o pedinte, ao receber o c042, manda 0x3000(quem aceitou).
        O servidor não grava nada por conta própria (antes isso fazia o 0x3000 do pedinte voltar com erro)."""
        mario = await self.client('mario', 'pw2')
        await mario.login()
        test = await self.client('test', 'pw1')
        await test.login()
        await test.send(bs.SVC_ADD_BUDDY, b'mario'.ljust(16, b'\0') + b'\0' * 20)
        await mario.send(bs.SVC_ADD_BUDDY, b'test'.ljust(16, b'\0') + b'\0' * 20)
        for c, other in ((test, b'mario'), (mario, b'test')):
            cmd, body = await c.recv()
            self.assertEqual((cmd, struct.unpack_from('<H', body)[0], body[2:2 + len(other)]), (bs.RET_ADD_BUDDY, 0, other))
            self.assertEqual((await c.recv())[0], bs.NTF_USER_STATE)
        self.assertEqual(sorted(self.repo.buddies), [('mario', '', 'test'), ('test', '', 'mario')])

    async def test_tunnel_and_saved_packets(self):
        mario = await self.client('mario', 'pw2')
        await mario.login()
        test = await self.client('test', 'pw1')
        await test.login()
        # pedido de amizade P2P c041 pelo túnel: chega como 0x2021 com remetente e apelido
        data = b'\0' * 8 + b'oi'
        await mario.send(bs.SVC_TUNNEL, struct.pack('<BHH', 1, 0xC041, len(data)) + data + struct.pack('<H', 2)
                         + b'test'.ljust(16, b'\0') + b'luigi'.ljust(16, b'\0'))
        cmd, body = await test.recv()
        self.assertEqual(cmd, bs.NTF_TUNNEL_PACKET)
        self.assertEqual(body, b'mario'.ljust(16, b'\0') + b'MarioZ'.ljust(12, b'\0') + struct.pack('<HH', 0xC041, len(data)) + data)
        self.assertEqual(len(self.repo.packets), 1)  # luigi offline + flag: guardado

        # 0x2000 cifrado para luigi offline
        plain = b'luigi'.ljust(16, b'\0') + struct.pack('<HH', 0xC011, 3) + b'ola'
        await test.send(bs.SVC_SAVE_PACKET, bs.encrypt_blocks(Client.crypto, test.key, plain))
        await asyncio.sleep(0.05)
        self.assertEqual(len(self.repo.packets), 2)

        luigi = await self.client('luigi', 'pw3')
        await luigi.login()
        cmd, body = await luigi.recv()
        self.assertEqual(cmd, bs.NTF_SAVE_PACKET)
        plain = bs.decrypt_blocks(Client.crypto, luigi.key, body)
        self.assertEqual(struct.unpack_from('<H', plain)[0], 2)
        self.assertEqual(plain[6:11], b'mario')
        self.assertEqual(struct.unpack_from('<HH', plain, 2 + 4 + 16 + 12 + 4), (0xC041, len(data)))
        await luigi.send(bs.SVC_SAVE_PACKET_ACK, struct.pack('<HII', 2, 1, 2))
        await asyncio.sleep(0.05)
        self.assertEqual(self.repo.packets, [])

    async def test_remove_group_search(self):
        self.repo.buddies = [('test', '', 'mario')]
        test = await self.client('test', 'pw1')
        await test.login()
        await test.recv()
        await test.send(bs.SVC_GROUP_BUDDY, struct.pack('<H', 1) + b'mario'.ljust(16, b'\0') + b'GM'.ljust(20, b'\0'))
        self.assertEqual(await test.recv(), (bs.RET_GROUP_BUDDY, struct.pack('<H', 0)))
        self.assertEqual(self.repo.buddies, [('test', 'GM', 'mario')])
        await test.send(bs.SVC_RENAME_GROUP, b'GM'.ljust(20, b'\0') + b'Staff'.ljust(20, b'\0'))
        self.assertEqual(await test.recv(), (bs.RET_RENAME_GROUP, struct.pack('<H', 0)))
        self.assertEqual(self.repo.buddies, [('test', 'Staff', 'mario')])
        await test.send(bs.SVC_SEARCH, b'Mari'.ljust(12, b'\0') + b'\0' * 8 + struct.pack('<HH', 0, 10))
        cmd, body = await test.recv()
        self.assertEqual((cmd, struct.unpack_from('<HH', body)), (bs.RET_SEARCH, (0, 1)))
        self.assertEqual(body[4:9], b'mario')
        await test.send(bs.SVC_REMOVE_BUDDY, b'mario'.ljust(16, b'\0'))
        self.assertEqual(await test.recv(), (bs.RET_REMOVE_BUDDY, struct.pack('<H', 0) + b'mario'.ljust(16, b'\0')))
        await test.send(bs.SVC_REMOVE_BUDDY, b'mario'.ljust(16, b'\0'))
        self.assertEqual((await test.recv())[1][:2], struct.pack('<H', bs.NOT_FOUND))

    async def test_udp_token_and_duplicate_login(self):
        test = await self.client('test', 'pw1')
        _, body = await test.login()
        token = struct.unpack_from('<I', body, 2)[0]
        self.assertTrue(await self.buddy.udp_token(token, ('10.0.0.9', 40000)))
        cmd, body = await test.recv()  # endereço observado != declarado
        self.assertEqual((cmd, body), (bs.NTF_VIP_IPPORT, bytes([10, 0, 0, 9]) + struct.pack('>H', 40000)))
        self.assertFalse(await self.buddy.udp_token(token + 1, ('10.0.0.9', 40000)))
        again = await self.client('test', 'pw1')
        await again.login()
        self.assertEqual(await test.recv(), (bs.NTF_CLOSE_CONNECTION, b'\0\0'))

    async def test_notice_after_login(self):
        self.buddy.notice = [['Aviso', 'Bem vindo']]
        c = await self.client('test', 'pw1')
        await c.login()
        self.assertEqual(await c.recv(), (bs.NTF_NOTICE, struct.pack('<H', 1) + b'Aviso	Bem vindo'))

    async def test_requires_login(self):
        c = await self.client('test', 'pw1')
        await c.send(bs.SVC_ADD_BUDDY, b'mario'.ljust(16, b'\0') + b'\0' * 20)
        await c.send(bs.SVC_PRECREDENTIAL)
        self.assertEqual((await c.recv())[0], bs.RET_PRECREDENTIAL)  # o ADD sem login não respondeu nada

    # ---- WC S2 v584 ----
    async def v584(self, user_id, nick):
        c = await self.client(user_id, None, cls=V584Client, nick=nick)
        if (await c.login())[0] == bs.RET_BUDDY_LIST:
            await c.recv()  # 0x1011 depois do 0x1012 (sem amigos o 0x1012 não vai)
        return c

    async def test_v584_login_list_and_states(self):
        self.repo.buddies = [('mario', '', 'test'), ('mario', '', 'luigi')]
        luigi = await self.v584('luigi', 'Luigi')
        mario = await self.client('mario', None, cls=V584Client, nick='MarioZ')
        cmd, body = await mario.login()
        self.assertEqual((cmd, struct.unpack_from('<H', body)[0], len(body)), (bs.RET_BUDDY_LIST, 2, 2 + 2 * 0x94))
        luigi_e, test_e = body[2:2 + 0x94], body[2 + 0x94:]
        self.assertEqual(luigi_e[:60], uid20('luigi') + w40('Luigi'))
        self.assertEqual(luigi_e[100:116], luigi.ext)  # online no v584: repassa o ext16 que ele mandou
        self.assertEqual(test_e[:100], uid20('test') + w40('test') + w40('G1'))
        self.assertEqual(test_e[100:104], struct.pack('<HH', 19, 19))  # offline: ext16 montado da TotalGrade
        cmd, body = await mario.recv()
        self.assertEqual((cmd, len(body), struct.unpack_from('<H', body)[0]), (bs.RET_LOGIN, 6, 0))
        cmd, body = await mario.recv()
        self.assertEqual(cmd, bs.NTF_USER_STATE)
        addr = bytes([127, 0, 0, 1]) + struct.pack('>H', 5000)
        self.assertEqual(body, struct.pack('<H', 2) + uid20('luigi') + b'\x01' + addr + addr + uid20('test') + b'\0')

    async def test_v584_requires_game_session(self):
        self.repo.not_in_game.add('mario')
        self.assertEqual(await (await self.client('mario', None, cls=V584Client)).login(),
                         (bs.RET_LOGIN, struct.pack('<H', bs.BAD_PASSWORD)))

    async def test_v584_add_remove_and_tunnel(self):
        mario = await self.v584('mario', 'MarioZ')
        luigi = await self.v584('luigi', 'Luigi')
        test = await self.client('test', 'pw1')
        await test.login()
        await mario.send(bs.SVC_ADD_BUDDY, uid20('luigi') + b'\0' * 32 + struct.pack('<H', 7))
        cmd, body = await mario.recv()
        self.assertEqual((cmd, len(body)), (bs.RET_ADD_BUDDY, 0x98))
        self.assertEqual(body[:22], struct.pack('<H', 0) + uid20('luigi'))
        self.assertEqual(body[-2:], struct.pack('<H', 7))
        self.assertEqual((await mario.recv())[1][:23], struct.pack('<H', 1) + uid20('luigi') + b'\x01')
        self.assertEqual(self.repo.buddies, [('mario', '', 'luigi')])

        data = b'\0' * 8 + b'oi'
        await mario.send(bs.SVC_TUNNEL, struct.pack('<BHH', 0, 0xC041, len(data)) + data + struct.pack('<H', 2)
                         + uid20('luigi') + uid20('test'))
        self.assertEqual(await luigi.recv(), (bs.NTF_TUNNEL_PACKET, uid20('mario') + w40('MarioZ')
                                              + struct.pack('<HH', 0xC041, len(data)) + data))
        await mario.send(bs.SVC_REMOVE_BUDDY, uid20('luigi'))
        self.assertEqual(await mario.recv(), (bs.RET_REMOVE_BUDDY, struct.pack('<H', 0) + uid20('luigi')))
        # o TH (test) não recebeu o c041 do v584: o próximo pacote dele é a resposta ao USER_STATE
        await test.send(bs.SVC_USER_STATE, b'mario'.ljust(16, b'\0'))
        self.assertEqual((await test.recv())[1][:19], struct.pack('<H', 1) + b'mario'.ljust(16, b'\0') + b'\x01')

    async def test_v584_saved_packets(self):
        mario = await self.v584('mario', 'MarioZ')
        plain = uid20('luigi') + struct.pack('<H', 4) + w40('oi')[:4]
        await mario.send(bs.SVC_SMS, bs.encrypt_blocks(Client.crypto, mario.key, plain))
        self.assertEqual(await mario.recv(), (bs.RET_SMS, struct.pack('<H', 0)))
        self.assertEqual(self.repo.packets[0]['Code'], bs.V584_SMS)
        luigi = await self.v584('luigi', 'Luigi')
        cmd, body = await luigi.recv()
        self.assertEqual(cmd, bs.NTF_SAVE_PACKET)
        rec = bs.decrypt_blocks(Client.crypto, luigi.key, body)[2:]
        self.assertEqual(rec[4:0x40], uid20('mario') + w40('MarioZ'))
        self.assertEqual(struct.unpack_from('<HH', rec, 0x44), (bs.V584_SMS, 4))
        self.assertEqual(rec[0x48:0x4C], w40('oi')[:4])


if __name__ == '__main__':
    unittest.main()
