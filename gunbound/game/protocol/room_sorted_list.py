from __future__ import annotations
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import RoomSortList
from gunbound.game import room_packets as rp
from gunbound.game.protocol.base import GameRecv, handler
from gunbound.game.protocol.enums import ClientPacket

ROOMS_PER_PAGE = 6   # corpo antigo sem quantidade: o TH pede 6 (array de 6 no cliente, 0x44830)
MAX_LIST_IDS = 12    # original: até 12 por pedido (0x2100 wRows < 13; 0x2101 len <= 0x18)


@handler(ClientPacket.CLI_ROOM_SORTED_LIST, channel=True)
class RoomSortedListRecv(GameRecv):
    """0x2100: u8 filtro (1 todas, 2 aguardando, 3..6 por modo) + u16 início + u16 quantidade (TH 0x432138, original
    len 5). A quantidade do cliente é respeitada até 12 (TH pede 6, v440/v495 pedem 9; nenhum lê além do que pediu).
    Corpos antigos só com o filtro ou filtro + u8 início continuam aceitos. Assina os ids devolvidos (0x21Fx)."""

    @inject
    async def handle(self, rooms=Provide['rooms']):
        sort_by = RoomSortList._value2member_map_.get(self.buf.require(1).read_uint8())
        if sort_by is None:
            return
        count = ROOMS_PER_PAGE
        if self.buf.remaining() >= 4:
            start, count = self.buf.read_uint16(), min(self.buf.read_uint16(), MAX_LIST_IDS)
        else:
            start = self.buf.read_uint8() if self.buf.remaining() >= 1 else 0
        found = await rooms.get_rooms(sort_by, start, count)
        rooms.watch(self.conn, [r.id for r in found])
        await self.conn.on_send(rp.room_list(found))


@handler(ClientPacket.CLI_ROOM_SPECIFIC_LIST, channel=True)
class RoomListByIdRecv(GameRecv):
    """0x2101: n x u16 id de sala (original 0x2101: n = len/2, até 12). Resposta 0x2103 com cada id na ordem pedida,
    sala vazia = u16 id + u8 0. Todos os ids pedidos são assinados, mesmo vazios (o 0x21F0 chega a quem listou o id)."""

    @inject
    async def handle(self, rooms=Provide['rooms']):
        ids = [self.buf.read_uint16() for _ in range(min(self.buf.remaining() // 2, MAX_LIST_IDS))]
        rooms.watch(self.conn, ids)
        await self.conn.on_send(rp.room_list_by_id([(i, rooms.get(i)) for i in ids]))
