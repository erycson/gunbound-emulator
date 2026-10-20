from __future__ import annotations
import asyncio
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable
from gunbound.base.enums import RoomStatus, RoomOptions, RoomMode, RANDOM_MAP, MAP_COUNT, TANK_RANDOM, TANK_COUNT
from gunbound.game.protocol.enums import ServerCode, ServerPacket
from gunbound.util import synchronized
from gunbound.game.stage_pos import spawn_xs

if TYPE_CHECKING:
    from gunbound.base.protocol import BasePackageSend
    from gunbound.game.client import ClientConnection
    from gunbound.game.managers import RoomManager

TEAM_A = 0
TEAM_B = 1
NO_WINNER = -1
# shortcut: vidas por jogador no modo Score não têm fonte WC; ajustar quando houver captura do servidor oficial.
SCORE_LIVES_PER_PLAYER = 2
SPAWN_Y = 0


@dataclass
class RoomPlayer:
    conn: 'ClientConnection'
    slot: int
    team: int = TEAM_A          # 0 = A, 1 = B
    ready: bool = False
    tank1: int = TANK_RANDOM    # 0x3200: primário
    tank2: int = TANK_RANDOM    # 0x3200: secundário (só modo Tag)
    alive: bool = True          # durante a partida (0x4100 / 0x4104)
    returned: bool = True       # voltou para a sala após o resultado (0x3232)

    def __post_init__(self):
        """Começa com o último tanque escolhido (0x3200 grava em ClientData[0:2])."""
        data = bytes((getattr(self.conn, 'data', None) or {}).get('game', {}).get('ClientData') or b'')
        if len(data) >= 2:
            self.tank1, self.tank2 = (t if t == TANK_RANDOM or t < TANK_COUNT else TANK_RANDOM for t in data[:2])


@dataclass
class GameState:
    """Estado de uma partida em andamento. Criado no start(), descartado no finish()."""
    map: int
    turn_order: list[int]
    tanks: dict[int, tuple[int, int]]                     # slot -> (primário, secundário) já sorteados
    spawns: dict[int, tuple[int, int]]
    score: dict[int, int] = field(default_factory=dict)   # team -> vidas (modo Score)
    winner: int = NO_WINNER
    result_sent: bool = False
    bonus_event: int = 0xFF                               # WCS2: tipo do bônus 0x4300 da partida (0xFF = nenhum)
    bonus_paid: set = field(default_factory=set)          # slots que já receberam o bônus

    def spawn_of(self, slot: int) -> tuple[int, int]:
        return self.spawns[slot]

    def tank1_of(self, p: RoomPlayer) -> int:
        return self.tanks[p.slot][0]

    def tank2_of(self, p: RoomPlayer) -> int:
        return self.tanks[p.slot][1]


def roll_tank(tank: int, rng: random.Random) -> int:
    return rng.randrange(TANK_COUNT) if tank == TANK_RANDOM else tank


class Room:
    """
    Estado de uma sala do lobby.

    API para os handlers (validações retornam ServerCode; SRV_OK = permitido):
      - can_join(conn, password) / join(conn)          -> 0x2110 / 0x2111
      - leave(conn) (via RoomManager.leave)            -> 0x2000(-1) / 0x3001 / desconexão -> 0x3020 / 0x3400
      - is_master(conn)                                -> 0x3100..0x3104, 0x3150, 0x3430
      - kick(master, slot)                             -> 0x3150 / 0x3FFF
      - set_team / set_ready / set_tanks               -> 0x3210 / 0x3230 / 0x3200
      - start_check(conn) / start() / finish()         -> 0x3430 / 0x3432 / 0x4413
      - on_dead(conn) / on_resurrect(conn)             -> 0x4100 / 0x4104 (retorna o time vencedor, se houver)
      - broadcast(packet, excepts)

    Regras GunBound: times A/B em todos os modos; para iniciar, todos (menos o mestre) prontos,
    pelo menos 2 jogadores e times com o mesmo número de jogadores. Tag usa o tanque secundário.
    Score: cada time tem vidas (SCORE_LIVES_PER_PLAYER por jogador) e o morto pode ressuscitar (0x4104).
    """

    def __init__(self, room_manager: 'RoomManager', id: int, owner: 'ClientConnection', options: RoomOptions):
        self.id = id
        self.room_manager = room_manager
        self.options: RoomOptions = options
        self.status: RoomStatus = RoomStatus.WAITING
        self.players: dict[int, RoomPlayer] = {}   # conn.id -> jogador
        self.owner: 'ClientConnection' = owner
        self.game: GameState | None = None
        self.lock = asyncio.Lock()
        self.rng = random.Random()
        self.result_hooks: list = []   # async (room, winner) chamados no 0x4412; quem cria a sala (ex.: Grand Prix) registra
        self.players[owner.id] = RoomPlayer(owner, slot=0, team=TEAM_A)
        owner.room = self

    # ---------- consultas (O(1) ou O(n<=8)) ----------
    def player_count(self) -> int:
        return len(self.players)

    def player(self, conn: 'ClientConnection') -> RoomPlayer | None:
        return self.players.get(conn.id)

    def player_by_slot(self, slot: int) -> RoomPlayer | None:
        return next((p for p in self.players.values() if p.slot == slot), None)

    def sorted_players(self) -> list[RoomPlayer]:
        return sorted(self.players.values(), key=lambda p: p.slot)

    def master_slot(self) -> int:
        return self.players[self.owner.id].slot

    def is_master(self, conn: 'ClientConnection') -> bool:
        return self.owner is conn

    def is_full(self) -> bool:
        return self.player_count() >= self.options.max_players()

    def is_waiting(self) -> bool:
        return self.status == RoomStatus.WAITING

    def team_counts(self) -> tuple[int, int]:
        a = sum(1 for p in self.players.values() if p.team == TEAM_A)
        return a, self.player_count() - a

    def is_team_mode(self) -> bool:
        return self.options.mode != RoomMode.SOLO

    # ---------- validações ----------
    def can_join(self, conn: 'ClientConnection', password: str | None) -> ServerCode:
        if self.status == RoomStatus.DESTROYING:
            return ServerCode.SRV_ROOM_NOT_FOUND
        if conn.id in self.players:
            return ServerCode.SRV_ROOM_NOT_FOUND
        if not self.is_waiting():
            return ServerCode.SRV_ROOM_IN_GAME
        if self.is_full():
            return ServerCode.SRV_ROOM_FULL
        if not self.options.check_password(password):
            return ServerCode.SRV_WRONG_PASSWORD
        return ServerCode.SRV_OK

    def start_check(self, conn: 'ClientConnection') -> str | None:
        """Motivo pelo qual a partida não pode começar, ou None se pode. Mestre GM (autoridade >= 99) joga sozinho."""
        if not self.is_master(conn):
            return "só o mestre inicia"
        if not self.is_waiting():
            return "sala já está em jogo"
        gm = int(conn.data['profile'].get('Authority') or 0) >= 99
        if self.player_count() < RoomOptions.MIN_PLAYERS and not gm:
            return "jogadores insuficientes"
        if any(not p.ready for p in self.players.values() if p.conn is not self.owner):
            return "nem todos estão prontos"
        a, b = self.team_counts()
        if a != b and not gm:
            return f"times desbalanceados ({a}x{b})"
        return None

    def can_start(self, conn: 'ClientConnection') -> bool:
        return self.start_check(conn) is None

    # ---------- mutações ----------
    @synchronized()
    async def join(self, conn: 'ClientConnection') -> RoomPlayer | None:
        """Adiciona o jogador no primeiro slot livre, no time com menos jogadores. Revalida sob lock (corrida de 2 joins)."""
        if not self.is_waiting() or self.is_full() or conn.id in self.players:
            return None
        used = {p.slot for p in self.players.values()}
        slot = next(i for i in range(self.options.max_players()) if i not in used)
        a, b = self.team_counts()
        player = RoomPlayer(conn, slot=slot, team=TEAM_A if a <= b else TEAM_B)
        self.players[conn.id] = player
        conn.room = self
        return player

    @synchronized()
    async def leave(self, conn: 'ClientConnection') -> RoomPlayer | None:
        """Remove o jogador. Passa o mestre para o próximo slot ou marca a sala vazia para destruir."""
        player = self.players.pop(conn.id, None)
        if player is None:
            return None
        conn.room = None
        if not self.players:
            self.status = RoomStatus.DESTROYING
        elif self.owner is conn:
            self.owner = self.sorted_players()[0].conn
            self.players[self.owner.id].ready = False  # mestre não usa "pronto"
        return player

    async def kick(self, master: 'ClientConnection', slot: int) -> RoomPlayer | None:
        """Só o mestre, só esperando, não expulsa a si mesmo nem GM."""
        if not self.is_master(master) or not self.is_waiting():
            return None
        target = self.player_by_slot(slot)
        if target is None or target.conn is master or int(target.conn.data['profile'].get('Authority') or 0) >= 99:
            return None
        return target if await self.room_manager.leave(target.conn) else None

    def set_team(self, conn: 'ClientConnection', team: int) -> bool:
        player = self.player(conn)
        if player is None or not self.is_waiting() or team not in (TEAM_A, TEAM_B):
            return False
        a, b = self.team_counts()
        size = self.options.max_players() // 2
        if team != player.team and (a if team == TEAM_A else b) >= size:
            return False  # time destino já tem metade da capacidade
        player.team = team
        player.ready = False
        return True

    def set_ready(self, conn: 'ClientConnection', ready: bool) -> bool:
        player = self.player(conn)
        if player is None or not self.is_waiting() or self.is_master(conn):
            return False
        player.ready = ready
        return True

    def set_tanks(self, conn: 'ClientConnection', tank1: int, tank2: int) -> bool:
        player = self.player(conn)
        if player is None or not self.is_waiting():
            return False
        player.tank1, player.tank2 = tank1, tank2
        player.ready = False if not self.is_master(conn) else player.ready
        return True

    def start(self) -> GameState:
        players = self.sorted_players()
        order = [p.slot for p in players]
        self.rng.shuffle(order)
        game_map = self.options.map if self.options.map != RANDOM_MAP else self.rng.randrange(1, MAP_COUNT)
        tanks = {p.slot: (roll_tank(p.tank1, self.rng), roll_tank(p.tank2, self.rng) if self.options.mode == RoomMode.TAG else TANK_RANDOM)
                 for p in players}
        xs = spawn_xs(game_map, len(players), self.rng)  # vagas do servidor original (data/stage_pos.txt)
        spawns = {p.slot: (x, SPAWN_Y) for p, x in zip(players, xs)}
        self.game = GameState(game_map, order, tanks, spawns)
        if self.options.mode == RoomMode.SCORE:
            a, b = self.team_counts()
            self.game.score = {TEAM_A: a * SCORE_LIVES_PER_PLAYER, TEAM_B: b * SCORE_LIVES_PER_PLAYER}
        self.status = RoomStatus.IN_GAME
        self._notify_state()
        for p in players:
            p.alive, p.ready, p.returned = True, False, False
        return self.game

    def on_dead(self, conn: 'ClientConnection') -> int:
        """Marca a morte e devolve o time vencedor (ou NO_WINNER). Morte repetida é ignorada."""
        player = self.player(conn)
        if player is None or self.game is None or not player.alive:
            return NO_WINNER
        player.alive = False
        if self.options.mode == RoomMode.SCORE:
            self.game.score[player.team] = max(0, self.game.score.get(player.team, 0) - 1)
            if self.game.score[player.team] == 0:
                return self._set_winner(1 - player.team)
            return NO_WINNER
        return self.check_elimination()

    def on_resurrect(self, conn: 'ClientConnection') -> bool:
        """Só no Score e enquanto o time ainda tem vidas."""
        player = self.player(conn)
        if player is None or self.game is None or player.alive or self.options.mode != RoomMode.SCORE:
            return False
        if self.game.score.get(player.team, 0) <= 0:
            return False
        player.alive = True
        return True

    def check_elimination(self) -> int:
        """Time sem ninguém vivo perde. Também usado quando alguém sai no meio da partida."""
        if self.game is None:
            return NO_WINNER
        alive = {p.team for p in self.players.values() if p.alive}
        if len(alive) == 1:
            return self._set_winner(alive.pop())
        if not alive:
            return self._set_winner(NO_WINNER)
        return NO_WINNER

    def _set_winner(self, team: int) -> int:
        if self.game is not None and self.game.winner == NO_WINNER:
            self.game.winner = team
        return team

    def finish(self) -> None:
        """Fim da partida (0x4412 processado): sala volta a aguardar; todos deixam de estar prontos."""
        self.status = RoomStatus.WAITING
        self.game = None
        self._notify_state()
        for p in self.players.values():
            p.ready = False
            p.alive = True

    # ---------- envio ----------
    def _notify_state(self) -> None:
        """0x21F7 para o lobby: 1 no início da partida, 0 no fim."""
        from gunbound.game import room_packets as rp
        self.room_manager.notify_lobby(self, rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_STATE, self).u8(rp.status_byte(self)))

    async def broadcast(self, packet: 'BasePackageSend', excepts: Iterable[int] | None = None) -> None:
        send_to_all(self.players.values(), packet, excepts, key=lambda p: p.conn)


def send_to_all(items, packet: 'BasePackageSend', excepts: Iterable[int] | None = None, key=lambda c: c) -> None:
    """Broadcast sem bloquear o loop: cada envio vira uma task com uma cópia do pacote (o on_send altera o buffer)."""
    skip = set(excepts) if excepts else ()
    for item in list(items):
        conn = key(item)
        if conn.id not in skip and not conn.closing:
            asyncio.create_task(conn.on_send(packet.clone()))
