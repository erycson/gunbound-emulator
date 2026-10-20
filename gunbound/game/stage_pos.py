"""
Posições de spawn do servidor original (GunBoundServ/*_stage_pos.txt, copiado para data/stage_pos.txt).
Linha: mapa,lado,vaga,x_min,x_max,? ; comentário. Lado = variante A/B do mapa (não é o time); a ordem das linhas é a ordem das vagas.
"""
from __future__ import annotations
import random
from functools import lru_cache
from pathlib import Path

STAGE_FILE = Path(__file__).resolve().parents[2] / 'data' / 'stage_pos.txt'
FALLBACK = (100, 1700)


def parse(text: str) -> dict[tuple[int, int], list[tuple[int, int]]]:
    table: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for line in text.splitlines():
        line = line.split(';', 1)[0].strip()
        if not line:
            continue
        parts = [int(p) for p in line.split(',')]
        if len(parts) < 5:
            continue
        lo, hi = sorted(parts[3:5])
        table.setdefault((parts[0], parts[1]), []).append((lo, hi))
    return table


@lru_cache(maxsize=1)
def table() -> dict[tuple[int, int], list[tuple[int, int]]]:
    try:
        return parse(STAGE_FILE.read_text(encoding='latin-1'))
    except OSError:
        print(f"[stage_pos] {STAGE_FILE} não encontrado; usando faixa padrão")
        return {}


def spawn_xs(game_map: int, count: int, rng: random.Random, side: int = 0) -> list[int]:
    """X de spawn de count jogadores: vagas distintas sorteadas (Rand_stage_pos) e X sorteado dentro da faixa."""
    # shortcut: sempre Lado A; o bit de lado nas opções da sala ainda é desconhecido
    ranges = table().get((game_map, side)) or table().get((0, 0)) or [FALLBACK]
    picks = rng.sample(range(len(ranges)), count) if count <= len(ranges) else [i % len(ranges) for i in range(count)]
    return [rng.randint(*ranges[i]) for i in picks]
