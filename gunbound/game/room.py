import asyncio
from gunbound.game.channel import Channel
from gunbound.game.protocol import RoomStatus, RoomSize, RoomMap, RoomMode
from gunbound.util import synchronized

class RoomOptions:
    def __init__(self, name: str, map: RoomMap, mode: RoomMode, size: RoomSize, password: str | None):
        self.name = name
        self.map = map
        self.mode = mode
        self.size = size
        self.password = password
        self.max_players: RoomSize = size

    def max_players(self) -> int:
        match self.size:
            case RoomSize.X1: return 2
            case RoomSize.X2: return 4
            case RoomSize.X3: return 6
            case RoomSize.X4: return 8

    def is_protected(self) -> bool:
        return self.password is not None

class Room:
    def __init__(self, manager, channel: Channel, id: int, owner, options: RoomOptions):
        self.id = id
        self.manager = manager
        self.channel = channel
        self.owner = owner
        self.options: RoomOptions = options
        self.status: RoomStatus = RoomStatus.WAITING
        self.players: dict[int, any] = {0: owner} | {i: None for i in range(1, options.max_players() - 1)}
        self.lock = asyncio.Lock()
    
    def player_count(self) -> int:
        return sum(1 for player in self.players.values() if player is not None)
    
    @synchronized()
    async def join(self, conn, position: int) -> bool:
        if self.status != RoomStatus.WAITING:
            return False
        if self.players[position] is not None:
            return False
        self.players[position] = conn
    
    @synchronized()
    async def kick_position(self, position: int) -> bool:
        if self.status != RoomStatus.WAITING:
            return False
        if position not in self.players:
            return False
        await self._remove_player(position)
        return True
    
    @synchronized()
    async def kick_player(self, conn):
        position = next((pos for pos, client in self.players.items() if client == conn), None)
        if position is not None:
            await self._remove_player(position)

    @synchronized()
    async def close(self) -> bool:
        """Fecha a sala, expulsando todos os jogadores e limpando recursos."""
        pass

    async def _remove_player(self, position: int):
        """Expulsa um jogador da sala. Implementa o envio do pacote de remoção"""
        if position not in self.players or self.players[position] is None:
            return

        player = self.players[position]
        player.room = None
        self.players[position] = None

        if self.owner == player:
            self.owner = next((p for p in self.players.values() if p is not None and p != player), None)
            if self.owner is None:
                await self.channel.destroy(self)

    async def _destroy(self):
        if self.status == RoomStatus.DESTROYING:
            return
        self.status = RoomStatus.DESTROYING

        """Destrói a sala e remove todos os jogadores."""
        for position, player in self.players.items():
            if player is not None:
                await self._remove_player(position)

        await self.channel.destroy(self)
