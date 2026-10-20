"""UDP administrativo 0xF010/0xF020/0xF030. Uso: python -m unittest tests.test_udp_admin"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from gunbound.game.managers.monitor import MonitorManager
from gunbound.util import BinaryReader


def mon(conn):
    m = MonitorManager.__new__(MonitorManager)
    m.client_manager = MagicMock(sessions={'mario': conn})
    return m


def fake_conn():
    c = MagicMock(data={'profile': {'Id': 7}})
    c.on_send, c.close = AsyncMock(), AsyncMock()
    return c


class UdpAdminTest(unittest.IsolatedAsyncioTestCase):
    async def test_force_logout(self):
        c = fake_conn()
        await mon(c).udp_force_logout(BinaryReader((7).to_bytes(4, 'little')))
        self.assertEqual(c.on_send.call_args[0][0].buf.getvalue(), b'\xff\x1f\x02\x00')
        c.close.assert_awaited()

    async def test_unknown_user_ignored(self):
        c = fake_conn()
        await mon(c).udp_force_logout(BinaryReader((8).to_bytes(4, 'little')))
        c.close.assert_not_awaited()

    async def test_gift_and_cash(self):
        c = fake_conn()
        await mon(c).udp_notify(BinaryReader((7).to_bytes(4, 'little')), 0x1050)
        self.assertEqual(c.on_send.call_args[0][0].buf.getvalue(), b'\x50\x10')
        with patch('gunbound.game.protocol.cash.CashRecv') as p:
            p.return_value.process = AsyncMock()
            await mon(c).udp_reload_cash(BinaryReader((7).to_bytes(4, 'little')))
            p.return_value.process.assert_called()


class UdpAddressTest(unittest.IsolatedAsyncioTestCase):
    """Datagrama de 4 bytes com o token do 0x1012: 0x101F só se o endereço observado diferir do 0x1010, uma vez."""
    async def check(self, net, addr):
        c = fake_conn()
        c.data.update(token=0x1234, net=net)
        t = MagicMock()
        m = mon(c)
        for _ in range(2):
            await m.udp_proc_initial_udp_recv(t, addr, BinaryReader((0x1234).to_bytes(4, 'little')))
        self.assertEqual(t.sendto.call_count, 2)  # eco sempre
        return c

    async def test_same_address(self):
        c = await self.check((int.from_bytes(bytes([10, 0, 0, 5]), 'little'), 8400), ('10.0.0.5', 8400))
        c.on_send.assert_not_awaited()

    async def test_nat(self):
        c = await self.check((int.from_bytes(bytes([10, 0, 0, 5]), 'little'), 8400), ('200.1.2.3', 9000))
        self.assertEqual(c.on_send.await_count, 1)
        self.assertEqual(c.on_send.call_args[0][0].buf.getvalue(), b'\x1f\x10' + bytes([200, 1, 2, 3]) + (9000).to_bytes(2, 'big'))


class UdpAllowTest(unittest.TestCase):
    def test_default_localhost_only(self):
        m = mon(fake_conn()); m.config = {}
        self.assertTrue(m.udp_allowed('127.0.0.1'))
        self.assertFalse(m.udp_allowed('192.168.0.5'))

    def test_configured_network(self):
        m = mon(fake_conn()); m.config = {'udp_allow': ['10.0.0.0/8']}
        self.assertTrue(m.udp_allowed('10.1.2.3'))
        self.assertFalse(m.udp_allowed('127.0.0.1'))


class DisconnectTest(unittest.IsolatedAsyncioTestCase):
    async def test_reset_calls_close(self):
        from gunbound.game.client import ClientConnection
        c = ClientConnection.__new__(ClientConnection)
        c.addr = 'x'
        c.reader = MagicMock(read=AsyncMock(side_effect=ConnectionResetError(10054, 'reset')))
        c.close = AsyncMock()
        await c.handler()
        c.close.assert_awaited()
