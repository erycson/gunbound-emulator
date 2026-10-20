"""
Posições de spawn dos servidores originais (data/, um arquivo por fase em Phase.stage_pos).

Os dois originais (2006 0x403d69 e 2007 0x404438) leem a linha como mapa,lado,vaga,Y,x_min,x_max e sorteiam X em
[x_min, x_max] (x_min se a faixa for vazia) com o Y da linha (2006 0x41638f / 2007 0x4193cc). Lado = variante do mapa
(A/B/C/D, bits 16-17 do settings), não o time.
- stage_pos_2007.txt (Rand_Stage_Pos.txt do servidor 2007, WC S1): nesse formato, com 4 lados (C/D = cópia de A/B) e Y
  nas plataformas altas (0 = cai do alto).
- stage_pos.txt (2006): colunas x_min,x_max,0/1 e lado B com a vaga sempre 0. Lido pelo original ele daria X fixo e
  Y = x_min; mantemos a leitura antiga (faixa X, Y 0, vaga = ordem das linhas), que é a que funciona no TH.
"""
from __future__ import annotations
import random
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / 'data'
DEFAULT = 'stage_pos.txt'
FALLBACK = (0, 100, 1700)   # (y, x_min, x_max)
SLOTS = 8


def parse(text: str) -> dict[tuple[int, int], list[tuple[int, int, int]]]:
    """(mapa, lado) -> 8 vagas (y, x_min, x_max). Formato 2006 se a última coluna for sempre 0/1."""
    rows = []
    for line in text.splitlines():
        line = line.split(';', 1)[0].strip()
        if line:
            parts = [int(p) for p in line.split(',')]
            if len(parts) >= 6:
                rows.append(parts[:6])
    old = all(r[5] in (0, 1) for r in rows)
    table: dict[tuple[int, int], list] = {}
    for m, side, slot, a, b, c in rows:
        if not (0 <= m < 20 and 0 <= side < 4 and 0 <= slot < SLOTS):
            continue  # o original ignora a linha (mapa < 20, lado < 4, vaga < 8)
        vagas = table.setdefault((m, side), [None] * SLOTS)
        if old:
            free = vagas.index(None) if None in vagas else None
            if free is not None:
                vagas[free] = (0, *sorted((a, b)), b)
        else:
            vagas[slot] = (a, b, c, b)
    return table  # vaga = (y, x_min, x_max, 5a coluna, que o original confere na validação)


@lru_cache(maxsize=None)
def table(name: str = DEFAULT) -> dict[tuple[int, int], list]:
    try:
        return parse((DATA / name).read_text(encoding='latin-1'))
    except OSError:
        print(f"[stage_pos] {DATA / name} não encontrado; usando faixa padrão")
        return {}


def initial_slots(players: list[tuple[int, int]], settings: int, rng: random.Random) -> dict[int, int]:
    """CalcInitialPos do original (2007 0x41a570 / 0x41aaa0): (vaga da sala, time) na ordem das vagas -> vaga do mapa.
    Até 6 jogadores usa as vagas 1..6 do mapa; 7 ou 8, as 0..7. Sem o bit 7 do settings ou tipo 2: sorteio.
    Tipo 0 (EvsW): cada time numa metade. Tipo 1 (Mix): vagas sorteadas e os times alternados da esquerda à direita."""
    n = 6 if len(players) <= 6 else SLOTS
    kind = settings & 0xF if settings & 0x80 else 2
    teams: dict[int, list[int]] = {}
    for slot, team in players:
        teams.setdefault(team, []).append(slot)
    a, b = (list(teams.values()) + [[], []])[:2]
    out: dict[int, int] = {}

    def probe(used: set) -> int:
        r = rng.randrange(n)
        while r in used:
            r = (r + 1) % n
        used.add(r)
        return r

    if kind == 0:
        left, right = (a, b) if rng.getrandbits(1) else (b, a)
        half = n // 2
        k = len(left) if len(left) > half else (half if len(right) <= half else n - len(right))
        left = left + [None] * (k - len(left))
        right = right + [None] * (n - k - len(right))
        rng.shuffle(left)
        rng.shuffle(right)
        out.update({s: i for i, s in enumerate(left) if s is not None})
        out.update({s: k + i for i, s in enumerate(right) if s is not None})
    elif kind == 1:
        used: set = set()
        for _ in players:
            probe(used)
        free = sorted(used)
        rng.shuffle(a)
        rng.shuffle(b)
        first, second = (a, b) if rng.getrandbits(1) else (b, a)
        while first or second:
            for team in (first, second):
                if team:
                    out[team.pop(0)] = free.pop(0)
    else:
        used = set()
        for slot, _ in players:
            out[slot] = probe(used)
    offset = 1 if n == 6 else 0
    return {s: m + offset for s, m in out.items()}


def spawn(game_map: int, side: int, map_slot: int, rng: random.Random, name: str = DEFAULT) -> tuple[int, int]:
    """(x, y) da vaga do mapa: X sorteado na faixa (x_min se vazia), Y da linha."""
    vagas = table(name).get((game_map, side)) or table(name).get((0, 0)) or [FALLBACK + (1,)]
    entry = vagas[map_slot] if map_slot < len(vagas) and vagas[map_slot] else next((v for v in vagas if v), FALLBACK + (1,))
    y, lo, hi = entry[:3]
    return (lo + rng.randrange(hi - lo + 1) if hi >= lo else lo), y


def out_of_range(settings: int, game_map: int) -> bool:
    """Parte da validação do original (0x4072f0) que não depende da tabela: posições >= 3 ou mapa >= 20."""
    return settings & 0xF >= 3 or game_map >= 20


def valid_settings(settings: int, game_map: int, name: str = DEFAULT) -> bool:
    """Validação do original (2007 0x4072f0): posições (bits 0-3) < 3, mapa < 20, lado < 4 e 5a coluna da vaga 0 > 0."""
    # shortcut: uma tabela para EvsW/Mix/Rand (os três arquivos do 2006 são iguais; o 2007 só tem o Rand)
    vagas = table(name).get((game_map, (settings >> 16) & 3))
    return settings & 0xF < 3 and game_map < 20 and bool(vagas) and bool(vagas[0]) and vagas[0][3] > 0


_rng = random.Random(1)
assert initial_slots([(0, 0), (1, 1)], 0x82, _rng).keys() == {0, 1}
for _kind in (0x80, 0x81, 0x82):
    for _n in range(1, 9):
        _p = [(s, s % 2) for s in range(_n)]
        _m = initial_slots(_p, _kind, _rng)
        assert len(set(_m.values())) == _n and all((1 if _n <= 6 else 0) <= v < (7 if _n <= 6 else 8) for v in _m.values())
_m = initial_slots([(s, s % 2) for s in range(6)], 0x80, _rng)  # EvsW 3x3: cada time numa metade (vagas 1-3 / 4-6)
assert {_m[s] <= 3 for s in (0, 2, 4)} != {_m[s] <= 3 for s in (1, 3, 5)} and len({_m[s] <= 3 for s in (0, 2, 4)}) == 1
