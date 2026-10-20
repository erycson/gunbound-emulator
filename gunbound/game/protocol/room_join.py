from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.game import room_packets as rp
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
CHANNEL_CAPACITY = 255  # Channel.add
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
    0x2130 (corpo vazio), como o original (2006 0x41a150, 2007 0x41d530): entra na primeira QuickStartRoom com vaga
    -> 0x2133 (mesmo corpo do 0x2111). Sem: cria uma (QuickStartOption/QuickStartMan) -> 0x2132; falhou, 0x2131 RTC 8.
    Times pela patente e início só com a sala completa ficam no Room.start_check.
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
        options = rooms.quick_options()
        room = None if options is None else await rooms.create(self.conn, options, quick=True)
        if room is None:
            await self.conn.on_send(Packet.new(ServerPacket.SRV_ROOM_QUICK_FAIL, rtc=QUICK_FAIL))
            return
        await self.conn.on_send(rp.quick_created(room, rooms.motd()))


@handler(ClientPacket.CLI_ROOM_LEAVE)
class RoomLeaveRecv(GameRecv):
    """
    0x3001 (SVC_LEAVE_WAIT_GAMEROOM): canal i16 (-1 = o atual). Sai da sala e reentra no canal, como o original
    (0x429626 chama a entrada de canal 0x40ef70 e responde 0x2001); os demais recebem 0x3020/0x3400 pelo RoomManager.
    Fora de sala ou sala em jogo: 0x2001 RTC 0x2009 (original 2007 0x41a380). Como o original só sai da sala se a
    entrada no canal der certo, o canal é conferido antes: inválido 0x2001 RTC 0x1D, cheio 0x2001 RTC 0x1001.
    """

    @inject
    async def handle(self, rooms=Provide['rooms'], channels=Provide['channels']):
        from gunbound.game.protocol.channel_join import ChannelJoinResp
        from gunbound.util.binary_buffer import BinaryReader
        if self.room is None or not self.room.is_waiting():
            await self.conn.on_send(Packet.new(ServerPacket.SRV_CHANNEL_JOIN, rtc=ServerCode.SRV_NOT_WAITING_ROOM))
            return
        channel_id = self.buf.read_int16() if self.buf.remaining() >= 2 else -1
        if not -1 <= channel_id <= 7:
            await self.conn.on_send(Packet.new(ServerPacket.SRV_CHANNEL_JOIN, rtc=ServerCode.SRV_DENIED))
            return
        target = channels.get(channel_id) if channel_id != -1 else None
        if target is not None and target is not self.conn.channel and target.size() >= CHANNEL_CAPACITY:
            await self.conn.on_send(ChannelJoinResp.channel_full(self.conn))
            return
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
