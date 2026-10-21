"""
Acerto do bot (docs/Bots.md): base pela patente, vezes um fator por dificuldade do tiro.

  base(n)   = ceil - (ceil - floor) * e^(-k*n)        n = patente normalizada, 0 pintinho .. 1 topo da versão
  acerto    = base(n) * PROD(1 - pen_i * (1 - damping*n))

O jogador bom sente só (1 - damping) de cada dificuldade. Tudo configurável em `bots.skill` do game server.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from gunbound.bot.profiles import Shot

DEFAULTS = {
    'floor': 0.25, 'ceil': 0.95, 'k': 3.0, 'damping': 0.5,
    'distance': 0.35,   # penalidade no alcance máximo (cresce linear com a distância)
    'wind': 0.30,       # penalidade com vento no máximo (força 0..1)
    'weather': 0.25,    # tornado/faixa de clima no caminho
    'hill': 0.15,       # alvo atrás de morro (tiro alto)
    'wall': 0.20,       # quica na parede e volta
    'ss': 0.10,         # tiro especial
    'angle_span': 135,  # graus fora da faixa boa até a penalidade de ângulo chegar ao máximo do tiro
    'angle_exp': 1.5,
    'too_close': 0.30,  # tiro que precisa de espaço, com o alvo colado (cai linear até min_dist)
}

# patente -> n: TH/S1 vão de 19 (pintinho) a -4 (dragão), admin 20; S2 de 1 (pintinho) a 41 (coroa), admin 0
GRADE_SCALE = {'TH': (19, -4, 20), 'WCS1': (19, -4, 20), 'WCS2': (1, 41, 0)}


def normalize(phase: str, grade: int) -> float:
    low, high, admin = GRADE_SCALE[phase]
    if grade == admin:
        return 1.0
    return min(1.0, max(0.0, (grade - low) / (high - low)))


def denormalize(phase: str, n: float) -> int:
    low, high, _ = GRADE_SCALE[phase]
    return round(low + (high - low) * min(1.0, max(0.0, n)))


def base(n: float, cfg=DEFAULTS) -> float:
    return cfg['ceil'] - (cfg['ceil'] - cfg['floor']) * math.exp(-cfg['k'] * n)


def angle_penalty(angle: float, shot: Shot, cfg=DEFAULTS) -> float:
    """0 dentro de uma faixa boa do tiro; tiro para baixo (< 0) também é 0, a distância já cobra. Cresce ^1.5 até
    `angle_span` graus fora da faixa (no máximo o tiro para trás rasante)."""
    if angle < 0 or any(a <= angle <= b for a, b in shot.angles):
        return 0.0
    d = min(min(abs(angle - a), abs(angle - b)) for a, b in shot.angles)
    return shot.max_pen * min(1.0, d / cfg['angle_span']) ** cfg['angle_exp']


@dataclass
class ShotSituation:
    angle: float              # 0 frente, 90 cima, > 90 para trás, < 0 para baixo
    distance: float           # em px
    max_distance: float       # alcance do mapa (o mais longe que dá)
    wind: float = 0.0         # força 0..1
    weather: bool = False     # faixa de clima no caminho
    behind_hill: bool = False
    wall: bool = False
    ss: bool = False


def penalties(s: ShotSituation, shot: Shot, cfg=DEFAULTS) -> dict[str, float]:
    p = {
        'distance': cfg['distance'] * shot.range * min(1.0, s.distance / s.max_distance) if s.max_distance else 0.0,
        'wind': cfg['wind'] * shot.wind * min(1.0, max(0.0, s.wind)),
        'angle': angle_penalty(s.angle, shot, cfg),
        'weather': cfg['weather'] if s.weather else 0.0,
        'hill': cfg['hill'] if s.behind_hill else 0.0,
        'wall': cfg['wall'] if s.wall else 0.0,
        'ss': cfg['ss'] if s.ss else 0.0,
        'too_close': cfg['too_close'] * (1 - s.distance / shot.min_dist) if s.distance < shot.min_dist else 0.0,
    }
    return {k: min(0.95, v) for k, v in p.items() if v > 0}


def hit_chance(n: float, s: ShotSituation, shot: Shot, cfg=DEFAULTS) -> float:
    chance = base(n, cfg)
    for pen in penalties(s, shot, cfg).values():
        chance *= 1 - pen * (1 - cfg['damping'] * n)
    return chance


def config(server_config) -> dict:
    return {**DEFAULTS, **((server_config.get('bots') or {}).get('skill') or {})}
