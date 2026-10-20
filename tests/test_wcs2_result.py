"""WCS2 resultado 0x4412 (contagens) -> 0x4415 (gold/GP). Uso: python -m unittest tests.test_wcs2_result -v"""
import struct
import unittest
from unittest import mock
from gunbound.base.enums import RoomOptions, RoomMode
from gunbound.game.protocol import game_play
from gunbound.game.protocol.wcs2 import result
from gunbound.util import BinaryReader
from tests.test_rooms_shop import FakeConn, manager, settle
from tests.test_wcs2_bonus import Repo


def record(slot, counts, win, bonus=0):
    return bytes([slot, *counts, 0]) + struct.pack('<HIIBB', 0, 0, 0, win, bonus)


class ResultTest(unittest.IsolatedAsyncioTestCase):
    def test_parse_and_reward(self):
        body = struct.pack('<H', 2) + record(0, [0, 1, 1, 0, 0, 0, 0, 0, 0], 1) + record(1, [0] * 8 + [1], 0)
        rows = result.parse(BinaryReader(body))
        self.assertEqual([r['slot'] for r in rows], [0, 1])
        cfg = {'gold_factor': 100, 'score_factor': 100}
        self.assertEqual(result.reward(rows[0], cfg), (100 + 50 + 100, 1 + 1 + 2))
        self.assertEqual(result.reward(rows[1], cfg), (-50 + 30, -1))

    async def test_handler_sends_4415_then_4413(self):
        a, b = FakeConn('a'), FakeConn('b')
        a.server.config = {'phase': 'WCS2', 'gold_factor': 200, 'score_factor': 100}
        b.server = a.server
        room = await manager().create(a, RoomOptions('sala', RoomMode.SOLO, 2, None))
        await room.join(b)
        room.start()
        slot_a, slot_b = room.player(a).slot, room.player(b).slot
        body = struct.pack('<H', 2) + record(slot_a, [0, 0, 1, 0, 0, 0, 0, 0, 0], 1) + record(slot_b, [0] * 9, 0)
        repo = Repo()
        with mock.patch.object(game_play, 'decrypt_blocks', lambda conn, data, cmd: BinaryReader(data)):
            await game_play.GameResultRecv(a, BinaryReader(body)).handle(inventory_repository=repo, user_repository=repo)
        self.assertEqual(repo.money, {'a': 300, 'b': 60})
        await settle()
        cmds = b.cmds()
        self.assertLess(cmds.index(result.SRV_GAME_REWARD), cmds.index(0x4413))
        pkt = b.last(result.SRV_GAME_REWARD)
        self.assertEqual(struct.unpack_from('<hBI', pkt, 2), (2, slot_a, 300))
        self.assertEqual(pkt[-1], slot_a)  # MVP: mais gold
        self.assertEqual(repo.points[('b', 'RenaPoints')], result.DEFAULT_GAME_POINTS['RenaPoints'])


def classic(slot, gold, gp):
    """Registro do 0x4412 do original (18 bytes): u8 slot, i32 gold, i16 evento, i16 GP, i32 tiros, i32 dano, u8 vitória."""
    return struct.pack('<BihhiiB', slot, gold, 0, gp, 0, 0, 1)


class ClassicResultTest(unittest.IsolatedAsyncioTestCase):
    async def play(self, rows):
        a, b = FakeConn('a'), FakeConn('b')
        a.server.config = {'gold_factor': 100, 'score_factor': 100}
        b.server = a.server
        room = await manager().create(a, RoomOptions('sala', RoomMode.SOLO, 2, None))
        await room.join(b)
        room.start()
        slots = [room.player(a).slot, room.player(b).slot]
        body = struct.pack('<H', len(rows)) + b''.join(classic(slots[i], g, s) for i, (g, s) in enumerate(rows))
        repo = Repo()
        repo.abnormal = []
        async def insert_abnormal_update(*args):
            repo.abnormal.append(args)
        repo.insert_abnormal_update = insert_abnormal_update
        with mock.patch.object(game_play, 'decrypt_blocks', lambda conn, data, cmd: BinaryReader(data)):
            await game_play.GameResultRecv(a, BinaryReader(body)).handle(inventory_repository=repo, user_repository=repo)
        return a, repo

    async def test_negative_gp_and_log(self):
        a, repo = await self.play([(3500, 10), (50, -3)])
        self.assertEqual((repo.money, repo.score), ({'a': 3500, 'b': 50}, {'a': 10, 'b': -3}))  # GP negativo continua negativo
        self.assertEqual(repo.abnormal, [('a', 'a', 10, 3500)])                                # acima de 3000: só log
        self.assertFalse(a.closing)

    async def test_drop_discards_everything(self):
        a, repo = await self.play([(100, 5), (7000, 0)])
        self.assertEqual((repo.money, repo.score, a.closing), ({}, {}, True))  # derruba o mestre, ninguém recebe


if __name__ == '__main__':
    unittest.main()
