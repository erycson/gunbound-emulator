from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING
from dependency_injector.providers import Configuration, Factory
from gunbound.base.enums import RoomSortList, RoomStatus, RoomOptions, RoomMode
from gunbound.util import synchronized
from gunbound.game.protocol.enums import ServerPacket

if TYPE_CHECKING:
    from gunbound.game.room import Room
    from gunbound.game.client import ClientConnection
    from gunbound.game_server import GameServer

MAX_ROOMS = 300
SORT_MODE = {
    RoomSortList.SOLO: RoomMode.SOLO,
    RoomSortList.SCORE: RoomMode.SCORE,
    RoomSortList.TAG: RoomMode.TAG,
    RoomSortList.JEWEL: RoomMode.JEWEL,
}


class RoomManager:
    def __init__(self, server: 'GameServer', config: Configuration, room_factory: Factory['Room']):
        self.server = server
        self.config = config
        self.room_factory = room_factory
        self.rooms: dict[int, Room] = {}
        self.lock = asyncio.Lock()
        self.quick_min_players = 1          # /qsman (só informativo, como no original)
        self.quick_mode: RoomMode | None = None  # /qsopt
        self.room_motd: str | None = None   # /motd -r

    def motd(self) -> str:
        return self.room_motd if self.room_motd is not None else self.config['announcement']

    def size(self) -> int:
        return len(self.rooms)

    def get(self, id: int) -> Room | None:
        room = self.rooms.get(id)
        return room if room is not None and room.status != RoomStatus.DESTROYING else None

    @synchronized()
    async def create(self, owner: 'ClientConnection', options: RoomOptions, grandprix=None) -> Room | None:
        from gunbound.game import room_packets as rp
        if len(self.rooms) >= MAX_ROOMS:
            return None
        id = next(i for i in range(len(self.rooms) + 1) if i not in self.rooms)
        room = self.rooms[id] = self.room_factory(room_manager=self, id=id, owner=owner, options=options)
        room.channel, room.grandprix = getattr(owner, 'channel', None), grandprix
        self.notify_lobby(room, rp.lobby_room_created(room))
        return room

    @synchronized()
    async def destroy(self, room: Room) -> bool:
        from gunbound.game import room_packets as rp
        if self.rooms.pop(room.id, None) is None:
            return False
        self.notify_lobby(room, rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_DESTROYED, room))
        return True

    def notify_lobby(self, room: Room, packet) -> None:
        """
        0x21F0..0x21F7 para quem está no canal da sala sem sala (lobby). Salas de Grand Prix ficam de fora, como no original.
        shortcut: o original (0x414890) só envia a quem pediu a lista nos últimos 30 s; aqui vai a todo o lobby.
        """
        channel = getattr(room, 'channel', None)
        if channel is None or getattr(room, 'grandprix', None):
            return
        ids = [c.id for c in channel.clients.values() if c.room is None]
        if ids:  # onlys vazio = todos no Channel.broadcast
            asyncio.get_running_loop().create_task(channel.broadcast(packet, onlys=ids))

    async def leave(self, conn: 'ClientConnection') -> Room | None:
        """
        Tira o jogador da sala atual e avisa os demais: 0x3020 (slot), 0x3400 se o mestre mudou e,
        no meio da partida, o vencedor (0x4410) se um time ficou sem ninguém. Destrói a sala vazia.
        """
        from gunbound.game import room_packets as rp
        room = conn.room
        if room is None:
            return None
        old_owner = room.owner
        player = await room.leave(conn)
        if player is None:
            return None
        if room.status == RoomStatus.DESTROYING:
            await self.destroy(room)
            return room
        self.notify_lobby(room, rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_PLAYERS, room).u8(room.player_count()))
        await room.broadcast(rp.player_left(player.slot))
        if room.owner is not old_owner:
            await room.broadcast(rp.host_change(room))
        if room.game is not None and room.game.winner == -1 and room.check_elimination() != -1:
            await room.broadcast(rp.winner(room.game.winner))
        return room

    async def get_rooms(self, sort_by: RoomSortList, start: int = 0, per_page: int = 6) -> list[Room]:
        """Filtra pelo critério da lista (todas, aguardando ou por modo) e pagina a partir do índice inicial."""
        rooms = (r for r in self.rooms.values() if r.status != RoomStatus.DESTROYING)
        if sort_by == RoomSortList.WAITING:
            rooms = (r for r in rooms if r.status == RoomStatus.WAITING)
        elif sort_by in SORT_MODE:
            rooms = (r for r in rooms if r.options.mode == SORT_MODE[sort_by])
        rooms = sorted(rooms, key=lambda r: r.id)
        start = max(0, start)
        return rooms[start:start + per_page]

    def find_quick(self, mode: RoomMode | None = None) -> Room | None:
        """Quick start: primeira sala aguardando, sem senha, com vaga (e do modo pedido, se houver)."""
        mode = mode if mode is not None else self.quick_mode
        for r in sorted(self.rooms.values(), key=lambda r: r.id):
            if r.is_waiting() and not r.is_full() and not r.options.is_protected() and (mode is None or r.options.mode == mode):
                return r
        return None
