"""
Grand Prix do servidor original (GunBoundServ3.exe, via REA; ver docs/Grand Prix.md).
- Fila por grupo (GrandPrix_Personal.Category): fecha quando há `battle_player_count` jogadores de um grupo e
  outros tantos de um grupo diferente (0x414ff0). Cria "GrandPrixRoom" com o 1º como mestre (0x415210):
  grupo do mestre no time A, o outro no time B.
- Pontuação no fim (0x418940): pessoal por vitória/derrota; grupo pela diferença de pontos entre os grupos.
- Ranking recalculado a cada `rank_interval` s e guardado em memória (o original consulta a cada 300 s).
"""
from __future__ import annotations
import asyncio
import struct
import time
from typing import TYPE_CHECKING
from gunbound.base.enums import RoomMode, RoomOptions, RANDOM_MAP
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection
    from gunbound.game.room import Room

ROOM_NAME = 'GrandPrixRoom'
NICK_LEN = 12
DEFAULTS = {
    'enabled': False, 'battle_player_count': 1, 'mode': 'SOLO', 'stage': RANDOM_MAP, 'rank_interval': 300,
    'rankers': 10, 'personal_win_score': 10, 'personal_lose_score': -5, 'big_rank_difference': 100,
    'group_win_score_small': 10, 'group_lose_score_small': -10,
    'group_win_score_big_lower': 20, 'group_lose_score_big_higher': -20,   # zebra: grupo mais fraco venceu
    'group_win_score_big_higher': 5, 'group_lose_score_big_lower': -5,     # favorito venceu
}


def _int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


class GrandPrixManager:
    def __init__(self, config, room_manager, grandprix_repository):
        self.cfg = {**DEFAULTS, **(config.get('grandprix') or {})}
        self.rooms = room_manager
        self.repo = grandprix_repository
        self.queue: list[tuple['ClientConnection', int]] = []   # (conn, categoria), ordem de chegada
        self.groups: list[dict] = []
        self.people: list[dict] = []
        self.loaded_at = 0.0
        self.lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.cfg['enabled'])

    # ---------- ranking (0x1100 -> 0x1101) ----------
    async def ranking(self) -> None:
        if time.time() - self.loaded_at < self.cfg['rank_interval']:
            return
        self.loaded_at = time.time()
        await self.repo.refresh_ranks()
        self.groups, self.people = await self.repo.rankers(self.cfg['rankers'])

    @staticmethod
    def group_record(g: dict) -> bytes:
        rank = _int(g['Rank'])
        return struct.pack('<iiiiii', _int(g['Category']), _int(g['ScoreOnCalc']), rank, rank - _int(g['RankOld']),
                           _int(g['Win']), _int(g['Lose']))

    @staticmethod
    def person_record(p: dict) -> bytes:
        rank = _int(p['Rank'])
        return (struct.pack('<iiiiii', rank, rank - _int(p['RankOld']), _int(p.get('Category')), _int(p['Score']), _int(p['Win']),
                            _int(p['Lose'])) + p['Nickname'].encode('latin-1')[:NICK_LEN].ljust(NICK_LEN, b'\x00'))

    async def list_body(self, user_id: str, layout=None) -> bytes:
        """Layout lido pelo cliente em 0x4caeb1: grupos(24) + pessoas(36) + [u8 + meu grupo(24)] + [u8 + eu(24)]; o WCS2 alarga (phase.py)."""
        from gunbound.game import phase
        layout = layout or phase.load(phase.DEFAULT)
        await self.ranking()
        out = struct.pack('<H', len(self.groups)) + b''.join(layout.gp_group(self.group_record(g), _int(g['Category'])) for g in self.groups)
        out += struct.pack('<H', len(self.people)) + b''.join(layout.gp_person(self.person_record(p)) for p in self.people)
        mine = await self.repo.personal(user_id)
        group = next((g for g in self.groups if mine and _int(g['Category']) == _int(mine['Category'])), None)
        out += b'\x01' + layout.gp_group(self.group_record(group), _int(group['Category'])) if group else b'\x00'
        out += b'\x01' + layout.gp_me(self.person_record({**mine, 'Nickname': ''})) if mine else b'\x00'
        return out

    # ---------- fila (0x2140 / 0x2141) ----------
    async def begin(self, conn: 'ClientConnection') -> str | None:
        """Entra na fila. Retorna o motivo da recusa (None = ok)."""
        if not self.enabled:
            return 'Grand Prix desligado neste servidor'
        mine = await self.repo.personal(conn.data['profile']['Id'])
        category = _int(mine['Category']) if mine else 0
        if not category:
            return 'jogador sem grupo (GrandPrix_Personal.Category)'
        async with self.lock:
            self.cancel(conn)
            self.queue.append((conn, category))
            match = self.find_match(category)
        if match:
            await self.create_room(*match)
        return None

    def cancel(self, conn: 'ClientConnection') -> None:
        self.queue = [(c, g) for c, g in self.queue if c is not conn]

    def find_match(self, category: int):
        self.queue = [(c, g) for c, g in self.queue if not c.closing and c.room is None]
        n = self.cfg['battle_player_count']
        mine = [c for c, g in self.queue if g == category][:n]
        if len(mine) < n:
            return None
        for other in dict.fromkeys(g for c, g in self.queue if g != category):
            rivals = [c for c, g in self.queue if g == other][:n]
            if len(rivals) == n:
                chosen = set(mine + rivals)
                self.queue = [(c, g) for c, g in self.queue if c not in chosen]
                return (mine, category), (rivals, other)
        return None

    async def create_room(self, team_a, team_b) -> 'Room | None':
        from gunbound.game import room_packets as rp
        (a, cat_a), (b, cat_b) = team_a, team_b
        n = self.cfg['battle_player_count']
        options = RoomOptions(ROOM_NAME, RoomMode[self.cfg['mode']], 2 * n, None, map=self.cfg['stage'])
        room = await self.rooms.create(a[0], options, grandprix=(cat_a, cat_b))   # time A / time B
        if room is None:
            return None
        room.result_hooks.append(self.on_result)
        for team, members in ((0, a[1:]), (1, b)):
            for conn in members:
                player = await room.join(conn)
                if player is not None:
                    player.team = team
        for player in room.players.values():
            await player.conn.on_send(rp.join_state(room, player, self.rooms.motd()))
        return room

    # ---------- resultado ----------
    def group_scores(self, winner: int, cats: tuple[int, int]) -> tuple[int, int]:
        """(pontos do vencedor, pontos do perdedor) conforme 0x418994: diferença = pontos do vencedor - do perdedor."""
        score = {_int(g['Category']): _int(g['ScoreOnCalc']) for g in self.groups}
        diff = score.get(cats[winner], 0) - score.get(cats[1 - winner], 0)
        c, big = self.cfg, self.cfg['big_rank_difference']
        if diff >= big:
            return c['group_win_score_big_higher'], c['group_lose_score_big_lower']
        if diff <= -big:
            return c['group_win_score_big_lower'], c['group_lose_score_big_higher']
        return c['group_win_score_small'], c['group_lose_score_small']

    async def on_result(self, room: 'Room', winner: int) -> None:
        cats = getattr(room, 'grandprix', None)
        if not cats or winner not in (0, 1):
            return
        for p in room.players.values():
            won = p.team == winner
            await self.repo.add_personal(p.conn.data['profile']['Id'],
                                         self.cfg['personal_win_score' if won else 'personal_lose_score'], won)
        win, lose = self.group_scores(winner, cats)
        await self.repo.add_group(cats[winner], win, True)
        await self.repo.add_group(cats[1 - winner], lose, False)
