"""
Mira do bot (docs/Bots.md, estágio 2): terreno do .lnd, simulação do projétil e escolha de ângulo/força.

Cada cliente simula o tiro do C400 (fábrica 0x443310 do v584): a lista de impactos do pacote só move a câmera
(0x458c30). Então o bot escolhe ângulo e força e os humanos calculam explosão e dano; errar a conta aqui só erra a mira.
Projétil (0x445426..0x445671): pos = (x, y) << 8; v = power * 512 * (cos, -sin) / 100;
a = (vento_x, gravidade - vento_y) << 8 / 100, seno da tabela 0x5fd6b0 (5 casas). Gravidade por mobile (characterdata).

.lnd = u32 w, u32 h, w*h bytes (0 = ar), lido em tempo de execução do graphics.xfs do S1 (bots.graphics_xfs); nada
de mapa vai para o repositório.
"""
from __future__ import annotations
import importlib.util
import math
import random
import struct
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_XFS = ROOT.parent / 'clientes' / 'WC-S1-v495' / 'graphics.xfs'
# stage.dat do S1 (índice = mapa + 11 no lado B); o 0 (Cave) não tem B
STAGES = ('cave', 'mos', 'hok', 'metro', 'candy', 'babo', 'last', 'brick', 'kettle', 'star', 'facky')
# characterdata.dat (coluna 40) do v495, por índice de tanque do WC (Mage, Lightning, Aduka, J.Frog, Dragon); o resto 98
GRAVITY = {0x01: 90, 0x07: 90, 0x0D: 94, 0x0F: 92, 0x11: 90}
# shortcut: velocidade x5 ajustada aos 36 tiros da captura v584 (mediana ~25 px); falta achar no cliente o passo por
# frame que dá esse fator. Basta para a mira, porque quem recebe recalcula o tiro.
SPEED = 5
BARREL = 30          # px do pé até a boca do cano (os 6 s16 do C400 só mudam o início do tiro)
BODY = 18            # raio de acerto direto num tanque
CRATER = 30          # shortcut: raio fixo da cratera; o real é por tiro (characterdata), só desloca o chão do alvo
POWER = (40, 400)
ELEVATIONS = range(25, 86, 5)
_EXC = {37: 60181, 113: 92051, 132: 74315, 171: 15644, 216: -58778, 217: -60181, 240: -86602, 287: -95631,
        293: -92051, 310: -76605, 312: -74315, 351: -15644}  # onde a tabela do cliente difere do seno arredondado
_SIN = [_EXC.get(d, round(math.sin(math.radians(d)) * 100000)) / 100000 for d in range(360)]


def sin_times(deg: int, f: int) -> int:
    return int(_SIN[deg % 360] * f)


def cos_times(deg: int, f: int) -> int:
    return int(_SIN[(deg + 90) % 360] * f)


def stage_name(game_map: int, side: int) -> str | None:
    if not 0 <= game_map < len(STAGES):
        return None
    name = STAGES[game_map]
    return name + 'b' if side == 1 and game_map else name


@lru_cache(maxsize=4)
def _lnd(path: str, name: str) -> bytes | None:
    spec = importlib.util.spec_from_file_location('_xfs_reader', ROOT / 'tools' / 'xfs_sync' / 'xfs_reader.py')
    xr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(xr)
    with open(path, 'rb') as f:
        entry = next((e for e in xr.read_trailer(f)[1] if e.name.lower() == name + '.lnd'), None)
        return xr.read_entry(f, entry) if entry else None


class Terrain:
    def __init__(self, data: bytes):
        self.w, self.h = struct.unpack_from('<II', data)
        self.px = bytearray(data[8:8 + self.w * self.h])

    @classmethod
    def load(cls, path, game_map: int, side: int) -> Terrain | None:
        name = stage_name(game_map, side)
        if not name or not Path(path).is_file():
            return None
        data = _lnd(str(path), name)
        return cls(data) if data else None

    def solid(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and self.px[y * self.w + x] != 0

    def ground(self, x: int, y: int = 0) -> int | None:
        """Primeiro chão a partir de y, descendo (o cliente solta o tanque do alto do spawn)."""
        if not 0 <= x < self.w:
            return None
        return next((yy for yy in range(max(0, y), self.h) if self.px[yy * self.w + x]), None)

    def carve(self, cx: int, cy: int, r: int = CRATER) -> None:
        for y in range(max(0, cy - r), min(self.h, cy + r + 1)):
            dx = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
            lo, hi = max(0, cx - dx), min(self.w, cx + dx + 1)
            if lo < hi:
                self.px[y * self.w + lo:y * self.w + hi] = bytes(hi - lo)


def muzzle(angle: int) -> tuple[int, int]:
    """(bx, by) do C400: y para cima; muzzle = (x + bx, y - by)."""
    return cos_times(angle, BARREL), sin_times(angle, BARREL)


def fly(t: Terrain, x: int, y: int, angle: int, power: int, gravity: int, wind: tuple[int, int],
        bodies=(), steps: int = 6000) -> tuple[int, int] | None:
    """Onde o tiro cai (chão ou corpo de um tanque), ou None se sai do mapa."""
    bx, by = muzzle(angle)
    speed = power * 512 * SPEED
    vx, vy = int(cos_times(angle, speed) / 100), -int(sin_times(angle, speed) / 100)
    wp, wa = wind
    ax, ay = int(cos_times(wa, wp) * 256 / 100), int((gravity - sin_times(wa, wp)) * 256 / 100)
    px, py = (x + bx) << 8, (y - by) << 8
    near = BODY * BODY
    for _ in range(steps):
        px += vx
        py += vy
        cx, cy = px >> 8, py >> 8
        if cy >= t.h or cx < 0 or cx >= t.w:
            return None
        if t.solid(cx, cy) or any((cx - ox) ** 2 + (cy - oy) ** 2 <= near for ox, oy in bodies):
            return cx, cy
        vx += ax
        vy += ay
    return None


def best_shot(t: Terrain, me: tuple[int, int], target: tuple[int, int], gravity: int, wind: tuple[int, int],
              bodies=()) -> tuple[int, int, tuple[int, int] | None, int]:
    """(ângulo absoluto, força, impacto, erro em px) que leva o tiro mais perto do alvo."""
    x, y = me
    tx, ty = target
    aim = (tx, ty - BODY // 2)
    best = None
    for e in ELEVATIONS:
        angle = e if tx >= x else 180 - e

        def score(p):
            hit = fly(t, x, y, angle, p, gravity, wind, bodies)
            return (math.dist(hit, aim) if hit else 1e9), hit

        coarse = min(range(POWER[0], POWER[1] + 1, 10), key=lambda p: score(p)[0])
        for p in range(max(POWER[0], coarse - 9), min(POWER[1], coarse + 9) + 1):
            d, hit = score(p)
            if best is None or d < best[3]:
                best = (angle, p, hit, d)
    return best


def miss(rng: random.Random, power: int) -> int:
    """Força errada de 10 a 25%, para mais ou para menos."""
    f = rng.uniform(0.10, 0.25) * rng.choice((-1, 1))
    return max(POWER[0], min(POWER[1], round(power * (1 + f))))
