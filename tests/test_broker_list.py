"""0x1102 do broker: layout do TH (13 bytes no fim de cada entrada) e 0x1101 (lista por índice)."""
import struct
import unittest
from types import SimpleNamespace as N
from gunbound.broker.protocol.server_sorted_list import ServerSortedListResp, ServerSpecificListRecv
from gunbound.util import BinaryReader


def srv(index, name):
    return N(index=index, event=0, name=name, description='d', host='127.0.0.1', port=8360, users_online=3,
             users_max=9, grade_max=-4, grade_min=19, avatar_enabled=1, is_online=True)


class Conn:
    def __init__(self, th):
        self.th, self.sent = th, []

    async def on_send(self, pkt):
        self.sent.append(pkt.buf.getvalue())


class BrokerListTest(unittest.IsolatedAsyncioTestCase):
    def test_th_layout(self):
        servers = [srv(0, 'a'), srv(1, 'b')]
        wc = ServerSortedListResp.success(servers).buf.getvalue()
        th = ServerSortedListResp.success(servers, th=True).buf.getvalue()
        self.assertEqual(len(wc) - len(th), 6)
        self.assertEqual(len(th), 6 + 2 * (2 + 1 + 2 + 2 + 13))  # idx, evento, nome 1+1, descrição 1+1, 13 bytes
        self.assertEqual(th[-1], 1)  # online é o último byte da entrada

    async def test_specific_list(self):
        servers = [srv(0, 'a'), srv(1, 'b'), srv(2, 'c')]
        conn = Conn(th=True)
        await ServerSpecificListRecv(conn, BinaryReader(struct.pack('<3H', 2, 9, 0)), server=N(all=lambda: servers)).process()
        body = conn.sent[0]
        self.assertEqual(body[:6], struct.pack('<HHBB', 0x1102, 0, 1, 2))  # índice 9 pulado
        self.assertEqual(struct.unpack_from('<H', body, 6)[0], 2)

    async def test_too_many(self):
        conn = Conn(th=True)
        await ServerSpecificListRecv(conn, BinaryReader(b'\x00' * 34), server=N(all=lambda: [])).process()
        self.assertEqual(conn.sent[0], struct.pack('<HH', 0x1102, 7))


class LauncherStartTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_game_requires_login(self):
        from gunbound.broker.protocol.launcher import StartGameRecv
        conn = Conn(th=False)
        conn.logged_in = False
        await StartGameRecv(conn, BinaryReader(b'')).process()
        conn.logged_in = True
        await StartGameRecv(conn, BinaryReader(b'')).process()
        self.assertEqual([struct.unpack('<HH', b) for b in conn.sent], [(0x4001, 0x13), (0x4001, 0)])


if __name__ == '__main__':
    unittest.main()
