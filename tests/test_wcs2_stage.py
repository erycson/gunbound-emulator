"""WCS2 canal Stage (0x1111 tipo 2): sala de 1 jogador, 0x2103 com missão, 0x4520 -> 0x4410, 0x4412 de 30 bytes.
Uso: python -m unittest tests.test_wcs2_stage -v"""
import struct
import unittest
from unittest import mock
from gunbound.base.enums import RoomOptions, RoomMode
from gunbound.game import room_packets as rp
from gunbound.game.protocol import game_play
from gunbound.game.protocol.base import Packet
from gunbound.game.protocol.wcs2 import result
from gunbound.game.protocol.wcs2.bonus import StageMissionEndRecv
from gunbound.util import BinaryReader
from tests.test_rooms_shop import FakeConn, manager, settle


class StageTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.a = FakeConn('a')
        self.room = await manager().create(self.a, RoomOptions('missao', RoomMode.SOLO, 1, None, stage=(4, 1)))

    async def test_solo_room_starts_and_lists_mission(self):
        self.assertEqual((self.room.options.max_players(), self.room.options.sizes()), (1, (1, 2)))
        self.assertIsNone(self.room.start_check(self.a))
        await self.a.on_send(rp.write_list_entry(Packet.new(0x2103), self.room, in_list=True))
        self.assertEqual(self.a.last(0x2103)[-3:], struct.pack('<HB', 4, 1))  # u16 StageNum-1, u8 GameMode

    async def test_mission_end_sends_winner_once(self):
        self.room.start()
        sent = []

        async def announce(room, team):
            sent.append(team)
        with mock.patch.object(game_play, 'announce_winner', announce):
            await StageMissionEndRecv(self.a, BinaryReader(b'\x00')).handle()
            await StageMissionEndRecv(self.a, BinaryReader(b'\x01')).handle()  # segundo 0x4520: ignorado
            await settle()
        team = self.room.player(self.a).team
        self.assertEqual((self.room.game.winner, sent), (team, [team]))

    async def test_death_alone_loses(self):
        self.room.start()
        self.assertEqual(self.room.on_dead(self.a), 1 - self.room.player(self.a).team)

    def test_result_record_30(self):
        rec = bytes([0, *[0] * 9, 0]) + struct.pack('<HIIBB', 0, 0, 0, 1, 0) + struct.pack('<HBI', 4, 1, 777)
        rows = result.parse(BinaryReader(struct.pack('<H', 1) + rec), stage=True)
        self.assertEqual((len(rows), rows[0]['win'], rows[0]['stage_score']), (1, 1, 777))


if __name__ == '__main__':
    unittest.main()
