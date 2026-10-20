"""Grand Prix: 0x1100 ranking (0x428c26), 0x2140 entrar na fila (0x429340), 0x2141 sair (0x4294f9). Ver docs/Grand Prix.md."""
from __future__ import annotations
from dependency_injector.wiring import Provide, inject
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game import phase
from gunbound.game.protocol.enums import ClientPacket, ServerPacket


@handler(ClientPacket.CLI_GRANDPRIX_LIST, register=False)  # WCS1
class GrandPrixListRecv(GameRecv):
    @inject
    async def handle(self, grandprix=Provide['grandprix']):
        if not grandprix.enabled:
            return  # como o original sem Grand Prix: sem resposta
        body = await grandprix.list_body(self.user_id(), phase.of(self.conn))
        await self.conn.on_send(Packet.new(ServerPacket.SRV_GRANDPRIX_LIST, rtc=0).raw(body))


@handler(ClientPacket.CLI_ROOM_GRANDPRIX_BEGIN, channel=True, register=False)  # WCS1
class GrandPrixBeginRecv(GameRecv):
    """Sem resposta no original: o cliente espera a sala (0x2111) quando a partida fecha."""

    @inject
    async def handle(self, grandprix=Provide['grandprix']):
        if self.conn.room is not None:
            return
        reason = await grandprix.begin(self.conn)
        print(f"[{self.conn.addr}] SVC_ROOM_GRANDPRIX_BEGIN: {reason or 'na fila'}")


@handler(ClientPacket.CLI_ROOM_GRANDPRIX_CANCEL, register=False)  # WCS1
class GrandPrixCancelRecv(GameRecv):
    @inject
    async def handle(self, grandprix=Provide['grandprix']):
        grandprix.cancel(self.conn)
