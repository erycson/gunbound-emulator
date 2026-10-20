from __future__ import annotations
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import RoomSortList
from gunbound.game import room_packets as rp
from gunbound.game.protocol.base import GameRecv, handler
from gunbound.game.protocol.enums import ClientPacket

ROOMS_PER_PAGE = 6  # F2: o cliente se perde com mais de 6 salas por página


class RoomListBase(GameRecv):
    """filtro u8 (1 todas, 2 aguardando, 3..6 por modo) + índice inicial u8 opcional (0, 6, 12...)."""

    @inject
    async def handle(self, rooms=Provide['rooms']):
        sort_by = RoomSortList._value2member_map_.get(self.buf.require(1).read_uint8())
        if sort_by is None:
            return
        start = self.buf.read_uint8() if self.buf.remaining() >= 1 else 0
        await self.conn.on_send(rp.room_list(await rooms.get_rooms(sort_by, start, ROOMS_PER_PAGE)))


@handler(ClientPacket.CLI_ROOM_SORTED_LIST, channel=True)
class RoomSortedListRecv(RoomListBase):
    pass


@handler(ClientPacket.CLI_ROOM_SPECIFIC_LIST, channel=True)
class RoomListPageRecv(RoomListBase):
    """0x2101: sem layout conhecido; tratado como a lista paginada (mesma resposta 0x2103)."""
