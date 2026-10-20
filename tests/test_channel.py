"""Posições do canal: fixas enquanto o jogador está no canal (0x200E/0x200F usam a posição). Uso: python -m unittest tests.test_channel"""
import unittest
from gunbound.game.channel import Channel
from tests.test_gm import conn


class ChannelSlotsTest(unittest.IsolatedAsyncioTestCase):
    async def test_positions_stable(self):
        ch = Channel(None, 0)
        late, early, third = conn('late'), conn('early'), conn('third')
        early.id, late.id = 900, 100        # quem entra depois tem id menor: não pode empurrar a posição dos outros
        await ch.add(early)
        await ch.add(late)
        self.assertEqual((ch.get_client_position(early), ch.get_client_position(late)), (0, 1))
        await ch.remove(early)
        self.assertEqual(ch.get_client_position(late), 1)
        await ch.add(third)
        self.assertEqual(ch.get_client_position(third), 0)       # reaproveita a menor vaga livre
        self.assertEqual([p for p, _ in await ch.get_all()], [0, 1])
        self.assertEqual(ch.get_highest_channel_position(), 1)


if __name__ == '__main__':
    unittest.main()
