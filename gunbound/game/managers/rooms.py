import asyncio
from gunbound.game.client import ClientConnection
from gunbound.game.protocol import RoomSortList
from gunbound.game.protocol import RoomMode, RoomStatus
from gunbound.game.room import Room, RoomOptions
from gunbound.util import synchronized

class RoomManager:
    _instance = None

    """
    @todo Verificar limites de usuários por canal.
    @todo Verificar limites de salas por canal.
    """
    def __init__(self, game, config):
        self.game = game
        self.config = config
        self.clients: dict[int, ClientConnection] = {}
        self.rooms: dict[int, Room] = {}
        self.lock = asyncio.Lock()
    
    @classmethod
    def initialize(cls, game, config):
        if cls._instance is not None:
            raise RuntimeError("RoomManager já inicializado!")

        cls._instance = cls(game, config)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError("RoomManager não inicializado!")
        return cls._instance
    
    def size(self) -> int:
        return len(self.rooms)
    
    def generate_id(self) -> int:
        id = 0
        while id in self.rooms:
            id += 1
        return id
    
    @synchronized()
    async def add(self, client: ClientConnection) -> bool:
        if client.id in self.clients:
            # Usuário está tentando entrar no mesmo canal novamente
            return False
        elif client.channel is not None:
            # Sai do canal anterior
            await client.channel.remove(client)

        self.clients[client.id] = client
        client.channel = self
        return True
    
    @synchronized()
    async def remove(self, client: ClientConnection) -> bool:
        if client.id not in self.clients:
            return False
    
        del self.clients[client.id]
        client.channel = None
        return True
    
    @synchronized()
    async def create(self, owner: ClientConnection, options: RoomOptions) -> Room:
        id = self.generate_id()
        self.rooms[id] = Room(self.manager, self, id, owner, options)
        return self.rooms[id]
    
    @synchronized()
    async def destroy(self, room: Room) -> bool:
        if room.id in self.rooms:
            await self.rooms[room.id].close()
            del self.rooms[room.id]
            return True
        return False

    # Verificar se é necessário o lock aqui
    # @synchronized()
    async def get_rooms(self, sort_by: RoomSortList, current_page: int = 0, per_page: int = 9) -> list[Room]:
        """
        Filtra as salas com base no critério de ordenação e aplica paginação.
        """
        filtered = []
        for room in self.rooms.values():
            if room.status == RoomStatus.DESTROYING:
                continue

            match sort_by:
                case RoomSortList.ALL:
                    filtered.append(room)
                case RoomSortList.WAITING:
                    if room.status == RoomStatus.WAITING:
                        filtered.append(room)
                case RoomSortList.SOLO:
                    if room.options['type'] == RoomMode.SOLO:
                        filtered.append(room)
                case RoomSortList.SCORE:
                    if room.options['type'] == RoomMode.SCORE:
                        filtered.append(room)
                case RoomSortList.TAG:
                    if room.options['type'] == RoomMode.TAG:
                        filtered.append(room)
                case RoomSortList.JEWEL:
                    if room.options['type'] == RoomMode.JEWEL:
                        filtered.append(room)

        # Aplica paginação
        start_index = max(0, current_page * per_page)
        end_index = min(len(filtered), start_index + per_page)
        return filtered[start_index:end_index]
