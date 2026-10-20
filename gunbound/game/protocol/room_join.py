from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import RoomMode, RoomOptions, ROOM_SIZES
from gunbound.game import room_packets as rp
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.game.room import Room
    from gunbound.game.client import ClientConnection


async def enter_room(conn: 'ClientConnection', room: 'Room', motd: str, error_cmd: int,
                     success_cmd: int = ServerPacket.SRV_ROOM_JOIN) -> bool:
    """Entrada comum ao 0x2110 e ao quick start: 0x2111 para quem entra (0x21F5 é a contagem do lobby, não pré-aviso), 0x3010 para os outros."""
    player = await room.join(conn)
    if player is None:  # perdeu a corrida pela última vaga ou a partida começou
        await conn.on_send(rp.room_error(error_cmd, ServerCode.SRV_ROOM_FULL))
        return False
    room.room_manager.notify_lobby(room, rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_PLAYERS, room).u8(room.player_count()))
    await conn.on_send(rp.join_state(room, player, motd, success_cmd))
    await room.broadcast(rp.player_joined(player), excepts=[conn.id])
    return True


QUICK_ROOM_TITLE = "QuickStartRoom"  # 0x46abf4 do original
QUICK_FAIL = 8                     # RTC do 0x2131 no original


@handler(ClientPacket.CLI_ROOM_JOIN, channel=True)
class RoomJoinRecv(GameRecv):
    """0x2110: room_id u16 + senha (resto, terminada em 00). Erros em 0x2111: 0x0011 inexistente/senha, 0x2001 cheia."""

    @inject
    async def handle(self, rooms=Provide['rooms']):
        if self.conn.room is not None:
            return
        room_id = self.buf.require(2).read_uint16()
        rest = self.buf.read_bytes()
        password = rest.split(b'\x00', 1)[0].decode('latin-1') or None
        room = rooms.get(room_id)
        code = room.can_join(self.conn, password) if room is not None else ServerCode.SRV_ROOM_NOT_FOUND
        if code != ServerCode.SRV_OK:
            await self.conn.on_send(rp.room_error(ServerPacket.SRV_ROOM_JOIN, code))
            return
        await enter_room(self.conn, room, rooms.motd(), ServerPacket.SRV_ROOM_JOIN)


@handler(ClientPacket.CLI_ROOM_DETAIL, channel=True)
class RoomDetailRecv(GameRecv):
    """0x2104: room_id u16 -> 0x2105. Sala inexistente: sem resposta (F3)."""

    @inject
    async def handle(self, rooms=Provide['rooms']):
        room = rooms.get(self.buf.require(2).read_uint16())
        if room is not None:
            await self.conn.on_send(rp.room_detail(room))


@handler(ClientPacket.CLI_ROOM_QUICK_START, channel=True)
class RoomQuickStartRecv(GameRecv):
    """
    0x2130 (corpo vazio): entra na primeira sala livre -> 0x2133 (mesmo corpo do 0x2111).
    Sem sala: cria "QuickStartRoom" como o original (0x41a150/0x413c30) -> 0x2132; se não der para criar, 0x2131 RTC 8.
    Diferença: o original só procura em salas criadas pelo servidor; aqui qualquer sala livre também serve.
    """

    @inject
    async def handle(self, rooms=Provide['rooms']):
        if self.conn.room is not None:
            return
        room = rooms.find_quick()
        if room is not None:
            await enter_room(self.conn, room, rooms.motd(), ServerPacket.SRV_ROOM_QUICK_START,
                             ServerPacket.SRV_ROOM_QUICK_START)
            return
        size = rooms.quick_min_players if rooms.quick_min_players in ROOM_SIZES else RoomOptions.MAX_PLAYERS
        options = RoomOptions(QUICK_ROOM_TITLE, rooms.quick_mode or RoomMode.SOLO, size, None)
        room = await rooms.create(self.conn, options)
        if room is None:
            await self.conn.on_send(Packet.new(ServerPacket.SRV_ROOM_QUICK_FAIL, rtc=QUICK_FAIL))
            return
        await self.conn.on_send(rp.quick_created(room, rooms.motd()))


@handler(ClientPacket.CLI_ROOM_LEAVE, room=True)
class RoomLeaveRecv(GameRecv):
    """
    0x3001 (SVC_LEAVE_WAIT_GAMEROOM): canal i16 (-1 = o atual). Sai da sala e reentra no canal, como o original
    (0x429626 chama a entrada de canal 0x40ef70 e responde 0x2001); os demais recebem 0x3020/0x3400 pelo RoomManager.
    """

    @inject
    async def handle(self, rooms=Provide['rooms'], channels=Provide['channels']):
        from gunbound.game.protocol.channel_join import ChannelJoinResp
        from gunbound.util.binary_buffer import BinaryReader
        channel_id = self.buf.read_int16() if self.buf.remaining() >= 2 else -1
        await rooms.leave(self.conn)
        old = self.conn.channel
        if old is not None:
            position = old.get_client_position(self.conn)
            if await old.remove(self.conn):
                await old.broadcast(ChannelJoinResp.success_remove(position))
            self.conn.channel = None
            if channel_id == -1:
                channel_id = old.id
        from gunbound.game.protocol.channel_join import ChannelJoinRecv
        await ChannelJoinRecv(self.conn, BinaryReader(channel_id.to_bytes(2, 'little', signed=True)), channel_manager=channels).process()
