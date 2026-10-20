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


if __name__ == '__main__':
    unittest.main()
