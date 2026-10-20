from __future__ import annotations
import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable
from gunbound.base.enums import RoomStatus, RoomOptions, RoomMode, RANDOM_MAP, MAP_COUNT, TANK_RANDOM, TANK_COUNT, HIDDEN_TANKS
from gunbound.game.protocol.enums import ServerCode, ServerPacket
from gunbound.util import synchronized
from gunbound.game import stage_pos

if TYPE_CHECKING:
    from gunbound.base.protocol import BasePackageSend
    from gunbound.game.client import ClientConnection
    from gunbound.game.managers import RoomManager

TEAM_A = 0
TEAM_B = 1
NO_WINNER = -1
QUICK_TEAMS = (TEAM_A, TEAM_B, TEAM_B, TEAM_A, TEAM_A, TEAM_B, TEAM_B, TEAM_A)  # QuickStartRoom: times pela patente (2006 0x415b40)
ALTERNATE_TURNS = 0x80   # bit 7 do settings: ordem de turno alternando os times
RANDOM_STAGE_ZERO = 0.15     # chance do stage 0 no mapa aleatório (servidor original)


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
            from gunbound.game import phase  # import tardio: phase importa os handlers, que importam room
            tanks = phase.of(self.conn).tanks
            self.tank1, self.tank2 = (t if t in tanks else TANK_RANDOM for t in data[:2])


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


HIDDEN_RATIO = 2    # Tank.Hidden.Ratio do original (padrão 2 = 2%)


def by_grade(players: list) -> list:
    """Jogadores em ordem de slot reordenados do mais forte ao mais fraco, com a mesma seleção com troca do original
    (2006 0x415b40 / 2007 0x418be0, TotalGrade crescente): empates não ficam necessariamente na ordem de slot.
    No S2 a patente cresce para cima (Phase.higher_grade_better), então a ordem usa o valor negado."""
    from gunbound.game import phase  # import tardio: phase carrega os protocolos, que importam este módulo
    out = list(players)
    sign = -1 if out and phase.of(out[0].conn).higher_grade_better else 1
    grade = lambda p: sign * int((p.conn.data.get('game') or {}).get('TotalGrade') or 0)
    for i in range(len(out)):
        for j in range(i + 1, len(out)):
            if grade(out[j]) < grade(out[i]):
                out[i], out[j] = out[j], out[i]
    return out


def turn_order(players: list, rng: random.Random) -> list[int]:
    """Ordem de turno (slots). Com o bit 7: cada time do mais fraco ao mais forte, alternando os times a
    partir de um sorteado (2007 0x418be0). Sem o bit 7 o original enche a ordem com lixo (bug; o cliente sempre manda o
    bit 7): aqui fica aleatória."""
    ranked = by_grade(players)
    teams = [[p.slot for p in ranked if p.team == t][::-1] for t in (TEAM_A, TEAM_B)]
    if not teams[0] or not teams[1]:
        return teams[0] or teams[1]
    first = rng.getrandbits(1)
    order = []
    for pair in zip(teams[first], teams[1 - first]):
        order.extend(pair)
    longer = teams[first] if len(teams[first]) > len(teams[1 - first]) else teams[1 - first]
    return order + longer[len(order) // 2:]


def roll_tank(tank: int, rng: random.Random, ratio: float = HIDDEN_RATIO, pool: tuple = tuple(range(TANK_COUNT))) -> int:
    """Aleatório do original (2006/2007): rand%10000 < ratio% -> 0x11/0x12 (ocultos), senão rand&0xF (pool = Phase.random_tanks)."""
    if tank != TANK_RANDOM:
        return tank
    if rng.randrange(10000) < ratio * 100:
        return HIDDEN_TANKS[rng.getrandbits(1)]
    return rng.choice(pool)


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
    Score: cada time tem N/2+1 vidas (N = jogadores) e o morto pode ressuscitar (0x4104).
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
        self.last_stage = 0      # último mapa sorteado (o aleatório não repete)
        self.idle_since = time.time()  # sala+0xb0 do original: criação e fim de partida (sala ociosa, L8)
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
        """0x2110 (original 2006 0x414266): sala automática (QuickStart/GP) não entra pelo id; Authority >= 98 pula a senha."""
        if self.status == RoomStatus.DESTROYING or getattr(self, 'auto', False):
            return ServerCode.SRV_ROOM_NOT_FOUND
        if conn.id in self.players:
            return ServerCode.SRV_ROOM_NOT_FOUND
        if not self.is_waiting():
            return ServerCode.SRV_ROOM_IN_GAME
        if self.is_full():
            return ServerCode.SRV_ROOM_FULL
        if int(conn.data['profile'].get('Authority') or 0) < 98 and not self.options.check_password(password):
            return ServerCode.SRV_WRONG_PASSWORD
        return ServerCode.SRV_OK

    def start_check(self, conn: 'ClientConnection') -> str | None:
        """Motivo pelo qual a partida não pode começar, ou None se pode. Mestre GM (autoridade >= 99) joga sozinho."""
        if not self.is_master(conn):
            return "só o mestre inicia"
        if not self.is_waiting():
            return "sala já está em jogo"
        gm = int(conn.data['profile'].get('Authority') or 0) >= 99
        quick = getattr(self, 'quick', False)
        if quick:  # QuickStartRoom (original +0xbd): sem "pronto"; os times saem da patente
            for p, team in zip(by_grade(self.sorted_players()), QUICK_TEAMS):
                p.team = team
        elif any(not p.ready for p in self.players.values() if p.conn is not self.owner):
            return "nem todos estão prontos"
        stage = self.options.stage is not None  # missão do canal Stage: 1 ou 2 jogadores contra os dummies do cliente
        if self.player_count() < RoomOptions.MIN_PLAYERS and not gm and not stage:
            return "jogadores insuficientes"
        a, b = self.team_counts()
        if a != b and not gm and not stage:
            return f"times desbalanceados ({a}x{b})"
        if quick and not gm and self.player_count() != self.room_manager.quick_min_players:
            return "QuickStartRoom incompleta"  # 2006: total == QuickStartMan
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
        if self.options.settings & ALTERNATE_TURNS:
            order = turn_order(players, self.rng)
        else:
            order = [p.slot for p in players]
            self.rng.shuffle(order)
        from gunbound.game import phase  # import tardio: phase importa os handlers, que importam room
        positions = phase.of(players[0].conn).stage_pos
        game_map = self.options.map if self.options.map != RANDOM_MAP else self._random_stage(positions)
        pool = phase.of(players[0].conn).random_tanks
        tanks = {p.slot: (roll_tank(p.tank1, self.rng, pool=pool), roll_tank(p.tank2, self.rng, pool=pool) if self.options.mode == RoomMode.TAG else TANK_RANDOM)
                 for p in players}
        slots = stage_pos.initial_slots([(p.slot, p.team) for p in players], self.options.settings, self.rng)
        spawns = {s: stage_pos.spawn(game_map, self.options.side, m, self.rng, positions) for s, m in slots.items()}
        self.game = GameState(game_map, order, tanks, spawns)
        if self.options.mode == RoomMode.SCORE:
            # original (0x415b40): vidas = N/2+1 por time, gravadas nos bits 20-23 do settings que vai no 0x3432
            lives = len(players) // 2 + 1
            self.options.settings = (self.options.settings & ~0xF00000) | (lives & 0xF) << 20
            self.game.score = {TEAM_A: lives, TEAM_B: lives}
        self.status = RoomStatus.IN_GAME
        self._notify_state()
        for p in players:
            p.alive, p.ready, p.returned = True, False, False
        return self.game

    def _random_stage(self, positions: str = stage_pos.DEFAULT) -> int:
        """Mapa aleatório do original (0x415b40): 15% o stage 0, senão 1..10 sem repetir o anterior; lado sorteado."""
        if self.rng.random() < RANDOM_STAGE_ZERO:
            stage = 0
        else:
            r = self.rng.randrange(10)
            stage = r + 1 if r + 1 != self.last_stage else (r + 2) % 10 + 1
            self.last_stage = stage
        # o original sorteia rand&3; só os lados que existem na tabela (a de 2006 só tem A/B)
        sides = [s for s in range(4) if stage_pos.valid_settings((self.options.settings & ~0x30000) | s << 16, stage, positions)] or [0]
        self.options.settings = (self.options.settings & ~0x30000) | self.rng.choice(sides) << 16
        return stage

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
        if self.options.stage is not None:  # os dummies só existem no cliente: perde quando todos morrem; vence pelo 0x4520
            owner = self.player(self.owner)
            return self._set_winner(1 - (owner.team if owner else 0)) if not alive else NO_WINNER
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
        self.idle_since = time.time()
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
