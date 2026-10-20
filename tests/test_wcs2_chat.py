"""0x7500 -> 0x7501 (lista do XPChatComboBox). Uso: python -m unittest tests.test_wcs2_chat -v"""
import unittest
from gunbound.game.protocol.wcs2.chat_combo import ChatComboListRecv, SRV_CHAT_COMBO_LIST
from gunbound.util import BinaryReader
from tests.test_services import crypt_conn


class ChatComboTest(unittest.IsolatedAsyncioTestCase):
    async def run_recv(self, entries=None):
        c = crypt_conn('u')
        if entries is not None:
            c.server.config['chat_combo_entries'] = entries
        await ChatComboListRecv(c, BinaryReader(b'')).process()
        return c.last(SRV_CHAT_COMBO_LIST)

    async def test_no_config_empty_list(self):
        self.assertEqual((await self.run_recv())[2:], b'\x00\x00\x00\x00')

    async def test_entries_16_bytes(self):
        body = (await self.run_recv(['oi', 'x' * 20]))[2:]
        self.assertEqual(body[:4], b'\x00\x00\x02\x00')
        self.assertEqual(body[4:20], b'oi' + b'\x00' * 14)
        self.assertEqual(body[20:], b'x' * 16)
