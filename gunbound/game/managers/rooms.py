from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING
from dependency_injector.providers import Configuration, Factory
from gunbound.base.enums import RoomSortList, RoomStatus, RoomOptions, RoomMode
from gunbound.util import synchronized
from gunbound.game.protocol.enums import ServerPacket

LOBBY_WATCH_SECONDS = 30  # original 0x414890: avisos de sala só para quem pediu a lista há até 30 s
# IdleRoomCloseTime/IdleRoomWarnTime/RoomCloseMsg/RoomCloseWarnMsg do Setting; padrões do original quando a chave falta
IDLE_ROOM = {'close': 1200, 'warn': 1140, 'close_msg': '', 'warn_msg': ''}
QUICK_START = {'man': 6, 'option': 0x451C2}  # padrões do original 2006/2007 (o Setting.txt do pacote "Season 2 server" tinha man 0: QuickStart sempre falha)

if TYPE_CHECKING:
    from gunbound.game.room import Room
    from gunbound.game.client import ClientConnection
    from gunbound.game_server import GameServer

MAX_ROOMS = 300
QUICK_ROOM_TITLE = "QuickStartRoom"  # 0x46abf4 do original
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
        quick = {**QUICK_START, **(config.get('quick_start') or {})}
        self.quick_min_players = int(quick['man'])  # QuickStartMan (/qsman): vagas da QuickStartRoom
        self.quick_option = int(quick['option'])    # QuickStartOption: settings da QuickStartRoom
        self.quick_mode: RoomMode | None = None  # /qsopt: troca só os bits 18-19 do QuickStartOption
        self.room_motd: str | None = None   # /motd -r
        # quem listou cada id de sala (0x2100/0x2101) e quando: destino dos 0x21F0..0x21F7 (original 0x414720/0x414890)
        self.watchers: dict[int, dict['ClientConnection', float]] = {}

    def motd(self) -> str:
        return self.room_motd if self.room_motd is not None else self.config['announcement']

    def size(self) -> int:
        return len(self.rooms)

    def get(self, id: int) -> Room | None:
        room = self.rooms.get(id)
        return room if room is not None and room.status != RoomStatus.DESTROYING else None

    @synchronized()
    async def create(self, owner: 'ClientConnection', options: RoomOptions, grandprix=None, auto: bool = False,
                     quick: bool = False) -> Room | None:
        from gunbound.game import room_packets as rp
        if len(self.rooms) >= MAX_ROOMS:
            return None
        id = next(i for i in range(len(self.rooms) + 1) if i not in self.rooms)
        room = self.rooms[id] = self.room_factory(room_manager=self, id=id, owner=owner, options=options)
        room.channel, room.grandprix = getattr(owner, 'channel', None), grandprix
        room.auto = auto or quick or grandprix is not None  # +0xbd do original: QuickStartRoom e GP, fora das listas e dos 0x21Fx
        room.quick = quick
        self.notify_lobby(room, rp.lobby_room_created(room))
        return room

    @synchronized()
    async def destroy(self, room: Room) -> bool:
        from gunbound.game import room_packets as rp
        if self.rooms.pop(room.id, None) is None:
            return False
        self.notify_lobby(room, rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_DESTROYED, room))
        return True

    async def idle_loop(self) -> None:
        """Timer de sala ociosa (L8), no ritmo do servidor original da fase."""
        from gunbound.game import phase
        layout = phase.load(self.config.get('phase') or phase.DEFAULT)
        while True:
            await asyncio.sleep(layout.idle_tick)
            await self.check_idle(layout.idle_waiting_only)

    async def check_idle(self, waiting_only: bool, now: float | None = None) -> None:
        """
        Original 2006 0x42f9f0 / 2007 0x436b30 (tick de 10 s nos dois): ociosa = agora - criação/fim de partida.
        Fecha para as 8 vagas sem olhar autoridade (2007 0x4367c0): GM também sai.
        > close: todos saem com 0x3FFF + RoomCloseMsg cru. Senão, warn_msg não vazia e >= warn: 0x5101 com o texto cru.
        Salas automáticas (QuickStart/GP) ficam de fora.
        """
        from gunbound.game.protocol.base import Packet
        cfg = {**IDLE_ROOM, **(self.config.get('idle_room') or {})}
        now = time.time() if now is None else now
        for room in list(self.rooms.values()):
            if room.status == RoomStatus.DESTROYING or getattr(room, 'auto', False):
                continue
            if waiting_only and (not room.is_waiting() or room.is_full()):
                continue
            idle = now - room.idle_since
            if idle > cfg['close']:
                print(f"[sala {room.id}] ociosa há {int(idle)} s: fechando")
                for player in list(room.players.values()):
                    await player.conn.on_send(Packet.new(ServerPacket.SRV_ROOM_KICKED).raw(cfg['close_msg'].encode('latin-1', 'replace')))
                    await self.leave(player.conn)
            elif cfg['warn_msg'] and idle >= cfg['warn']:
                await room.broadcast(Packet.new(ServerPacket.SRV_COMMAND).raw(cfg['warn_msg'].encode('latin-1', 'replace')))

    def watch(self, conn: 'ClientConnection', ids) -> None:
        """Assina conn nos ids da lista que acabou de receber (até 12), trocando a assinatura anterior (original 0x414720)."""
        for old in conn.data.pop('room_watch', ()):
            self.watchers.get(old, {}).pop(conn, None)
        now = time.monotonic()
        for room_id in ids:
            self.watchers.setdefault(room_id, {})[conn] = now
        conn.data['room_watch'] = tuple(ids)

    def notify_lobby(self, room: Room, packet) -> None:
        """
        0x21F0..0x21F7 para quem listou o id dessa sala há no máximo 30 s (original 0x414890: now <= time + 30).
        Salas automáticas (QuickStartRoom, GP) ficam de fora, como no original.
        """
        if getattr(room, 'auto', False):
            return
        since = time.monotonic() - LOBBY_WATCH_SECONDS
        watchers = self.watchers.get(room.id, {})
        for conn, at in list(watchers.items()):
            if conn.closing:
                del watchers[conn]
            elif at >= since:
                asyncio.get_running_loop().create_task(conn.on_send(packet))

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
        rooms = (r for r in self.rooms.values() if r.status != RoomStatus.DESTROYING and not getattr(r, 'auto', False))
        if sort_by == RoomSortList.WAITING:
            rooms = (r for r in rooms if r.status == RoomStatus.WAITING)
        elif sort_by in SORT_MODE:
            rooms = (r for r in rooms if r.options.mode == SORT_MODE[sort_by])
        rooms = sorted(rooms, key=lambda r: r.id)
        start = max(0, start)
        return rooms[start:start + per_page]

    def find_quick(self) -> Room | None:
        """QuickStart do original (0x41d530): primeira QuickStartRoom aguardando com menos de QuickStartMan jogadores."""
        for r in sorted(self.rooms.values(), key=lambda r: r.id):
            if getattr(r, 'quick', False) and r.is_waiting() and not r.is_full() and r.player_count() < self.quick_min_players:
                return r
        return None

    def quick_options(self) -> RoomOptions | None:
        """QuickStartRoom: título fixo, sem senha, settings = QuickStartOption, máx = QuickStartMan (1..8, senão falha).
        shortcut: tamanhos ímpares viram 8 (RoomOptions só tem 2/4/6/8); só muda se alguém usar QuickStartMan ímpar."""
        if not 1 <= self.quick_min_players <= 8:
            return None
        settings = self.quick_option
        if self.quick_mode is not None:  # /qsopt: opt = (opt & 0xFFF3FFFF) | bits do modo, sem o bit 22
            settings = (settings & ~0xC0000) | ((int(self.quick_mode) << 16) & 0xC0000)
        options = RoomOptions(QUICK_ROOM_TITLE, RoomMode.of_settings(settings), self.quick_min_players, None)
        options.settings = settings  # cru, como o original (o setter de modo acrescentaria o bit 22)
        return options
