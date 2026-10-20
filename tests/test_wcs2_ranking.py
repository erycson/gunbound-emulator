"""Ranking WCS2 (0x7040 -> 0x7041). Uso: python -m unittest tests.test_wcs2_ranking -v"""
import struct
import unittest
from gunbound.game.protocol.wcs2 import ranking
from gunbound.util import BinaryReader
from tests.test_gm import conn


def row(i, score, guild='G'):
    return {'Id': f'id{i}', 'Nickname': f'nick{i}', 'Guild': guild, 'Grade': 5, 'Score': score}


class FakeDb:
    def __init__(self, rows):
        self.rows, self.sql = rows, None

    async def fetch_all(self, sql, values=None):
        self.sql = sql
        return self.rows


class RankingTest(unittest.IsolatedAsyncioTestCase):
    async def ask(self, kind, flag, rows, me='id2'):
        c = conn('u')
        c.data = {'profile': {'Id': me}, 'game': {'Guild': 'G'}}
        db = FakeDb(rows)
        await ranking.RankingRecv(c, BinaryReader(bytes([kind, 3, flag]))).handle(db=db)
        return c.last(ranking.SRV_RANKING), db.sql

    async def test_top_list_with_my_position(self):
        pkt, sql = await self.ask(1, 1, [row(1, 3000), row(2, 2000)])
        self.assertIn('SeasonScore', sql)
        head = struct.pack('<HBBBH', 0x7041, 1, 3, 1, 2) + b'2000'.ljust(16, b'\x00') + b'\x02'
        first = struct.pack('<HH', 1, 5) + b'nick1'.ljust(12, b'\x00') + b'G'.ljust(8, b'\x00') + b'3000'.ljust(16, b'\x00')
        self.assertEqual(pkt[:len(head) + 40], head + first)
        self.assertEqual(len(pkt), len(head) + 2 * 40)

    async def test_my_rank_window(self):
        rows = [row(i, 10000 - i) for i in range(1, 301)]
        pkt, _ = await self.ask(0, 0, rows, me='id200')
        self.assertEqual(struct.unpack_from('<H', pkt, 5)[0], 200)
        first = 5 + 2 + 16 + 1
        self.assertEqual(pkt[first - 1], ranking.PAGE)
        self.assertEqual(struct.unpack_from('<H', pkt, first)[0], 150)  # começa PAGE/2 antes de mim

    async def test_outside_and_guild_query(self):
        pkt, sql = await self.ask(2, 1, [], me='x')
        self.assertIn('GROUP BY Guild', sql)
        self.assertEqual(pkt, struct.pack('<HBBBH', 0x7041, 2, 3, 1, 0) + b'\x00' * 16 + b'\x00')

    def test_registered_in_wcs2(self):
        from gunbound.game import phase
        self.assertIs(phase.WCS2.add[ranking.CLI_RANKING], ranking.RankingRecv)


if __name__ == '__main__':
    unittest.main()
