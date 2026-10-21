"""
Mira do bot (docs/Bots.md, estágio 2): terreno do .lnd, simulação do projétil e escolha de ângulo/força.

Cada cliente simula o tiro do C400 (fábrica 0x443310 do v584): a lista de impactos do pacote só move a câmera
(0x458c30). Então o bot escolhe ângulo e força e os humanos calculam explosão e dano; errar a conta aqui só erra a mira.
Projétil (0x445426..0x445671): pos = (x, y) << 8; v = power * 512 * (cos, -sin) / 100;
a = (vento_x, gravidade - vento_y) << 8 / 100, seno da tabela 0x5fd6b0 (5 casas). Gravidade por mobile (characterdata).

.lnd = u32 w, u32 h, w*h bytes (0 = ar). Vem de server/maps/ (tools/import_maps.py: um .lnd.gz por mapa e a tabela
stages-<versão>.txt de cada cliente; fora do git) ou, sem importação, do graphics.xfs do S1 (bots.graphics_xfs).
"""
from __future__ import annotations
import gzip
import importlib.util
import math
import random
import struct
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_XFS = ROOT.parent / 'clientes' / 'WC-S1-v495' / 'graphics.xfs'
MAPS = ROOT / 'maps'  # tools/import_maps.py
# stage.dat do S1 (índice = mapa + 11 no lado B); o 0 (Cave) não tem B. Os lados 2/3 (C/D) não estão no S1
STAGES = ('cave', 'mos', 'hok', 'metro', 'candy', 'babo', 'last', 'brick', 'kettle', 'star', 'facky')
# characterdata.dat (coluna 40) do v495, por índice de tanque do WC (Mage, Lightning, Aduka, J.Frog, Dragon); o resto 98
GRAVITY = {0x01: 90, 0x07: 90, 0x0D: 94, 0x0F: 92, 0x11: 90}
# shortcut: velocidade x5 ajustada aos 36 tiros da captura v584 (mediana ~25 px); falta achar no cliente o passo por
# frame que dá esse fator. Basta para a mira, porque quem recebe recalcula o tiro.
SPEED = 5
BARREL = 30          # px do pé até a boca do cano (os 6 s16 do C400 só mudam o início do tiro)
BODY = 18            # raio de acerto direto num tanque
SAFE = 60            # o tiro não pode cair tão perto do próprio bot (a explosão pega nele)
STEP = 4             # px por subpasso na colisão (o passo do tiro chega a 40 px e atravessaria paredes finas)
CRATER = 30          # shortcut: raio fixo da cratera; o real é por tiro (characterdata), só desloca o chão do alvo
POWER = (40, 400)
# clima (docs/Bots.md): coluna = x - w/4 < X < x + w/4 (0x454eb0). Tornado e espelho mudam o tiro; força,
# blackforce e elétrico só aumentam o dano de quem passa (+0x98/+0xa4/+0x308 vão para a explosão)
TORNADO_VX = 200 * SPEED  # piso do |vx| preso no tornado (0x470115), na escala do passo daqui
MIRROR_Y = 640            # o espelho do 0xc300 só rebate com Y >= 640 (0x471f66)
BOOSTS = {'force', 'blackforce', 'electric'}
UNSAFE = 1e9              # erro de tiro que sai do mapa ou cai em cima do bot/aliado
ELEVATIONS = range(25, 86, 5)
_EXC = {37: 60181, 113: 92051, 132: 74315, 171: 15644, 216: -58778, 217: -60181, 240: -86602, 287: -95631,
        293: -92051, 310: -76605, 312: -74315, 351: -15644}  # onde a tabela do cliente difere do seno arredondado
_SIN = [_EXC.get(d, round(math.sin(math.radians(d)) * 100000)) / 100000 for d in range(360)]


def sin_times(deg: int, f: int) -> int:
    return int(_SIN[deg % 360] * f)


def cos_times(deg: int, f: int) -> int:
    return int(_SIN[(deg + 90) % 360] * f)


def stage_name(game_map: int, side: int) -> str | None:
    if not 0 <= game_map < len(STAGES) or side not in (0, 1):
        return None
    name = STAGES[game_map]
    return name + 'b' if side == 1 and game_map else name


@lru_cache(maxsize=4)
def _stages(maps: str, version: str) -> dict[tuple[int, int], str] | None:
    path = Path(maps) / f'stages-{version}.txt'
    if not path.is_file():
        return None
    rows = (line.split() for line in path.read_text(encoding='utf-8').splitlines() if line.strip())
    return {(int(m), int(side)): name for m, side, name in rows}


@lru_cache(maxsize=8)
def _imported(path: str) -> bytes:
    return gzip.decompress(Path(path).read_bytes())


def load_map(game_map: int, side: int, version: str, maps=MAPS, xfs=DEFAULT_XFS) -> Terrain | None:
    """Terreno do mapa no cliente `version` (s1 ou v584). O v584 só tem lados A/B: grava lado = side % 2 (0x509716),
    então os lados C/D da sala usam o terreno de A/B. Sem a tabela importada dessa versão, a do S1; sem nenhuma, o
    graphics.xfs do S1."""
    if version == 'v584':
        side %= 2
    table = _stages(str(maps), version) or _stages(str(maps), 's1')
    if table is None:
        return Terrain.load(xfs, game_map, side)
    name = table.get((game_map, side))
    return Terrain(_imported(str(Path(maps) / f'{name}.lnd.gz'))) if name else None


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


def inside(cx: int, col) -> bool:
    _, x, w = col
    return x - w // 4 < cx < x + w // 4


def fly(t: Terrain, x: int, y: int, angle: int, power: int, gravity: int, wind: tuple[int, int],
        bodies=(), steps: int = 6000, weather=(), crossed: set | None = None) -> tuple[int, int] | None:
    """Onde o tiro cai (chão ou corpo de um tanque), ou None se sai do mapa. weather: colunas (tipo, x, w) do clima;
    crossed recebe os tipos que o tiro atravessou. Tornado (0x4715c0, 0x470115): prende o tiro, que fica sem gravidade
    e vento, com |vx| >= TORNADO_VX, e inverte o vx nas 2 primeiras saídas da coluna; solta na 3ª. Espelho
    (0x471d50): uma vez por entrada, com Y >= MIRROR_Y, inverte o vx e põe o tiro na borda da coluna."""
    bx, by = muzzle(angle)
    speed = power * 512 * SPEED
    vx, vy = int(cos_times(angle, speed) / 100), -int(sin_times(angle, speed) / 100)
    wp, wa = wind
    ax, ay = int(cos_times(wa, wp) * 256 / 100), int((gravity - sin_times(wa, wp)) * 256 / 100)
    px, py = (x + bx) << 8, (y - by) << 8
    near = BODY * BODY
    spin, turns, latched = None, 0, set()
    for _ in range(steps):
        n = max(abs(vx), abs(vy)) // (STEP << 8) + 1
        bounced = False
        for i in range(1, n + 1):
            cx, cy = (px + vx * i // n) >> 8, (py + vy * i // n) >> 8
            if cy >= t.h or cx < 0 or cx >= t.w:
                return None
            if t.solid(cx, cy):
                return cx, cy
            for k, col in enumerate(weather):
                if not inside(cx, col):
                    latched.discard(k)
                    continue
                if crossed is not None:
                    crossed.add(col[0])
                if col[0] == 'tornado' and spin is None:
                    spin, turns = col, 0
                elif col[0] == 'mirror' and k not in latched and cy >= MIRROR_Y:
                    latched.add(k)
                    vx = -vx
                    px, py = (col[1] + (col[2] // 4 if vx > 0 else -(col[2] // 4))) << 8, cy << 8
                    bounced = True
                    break
            if bounced:
                break
        if any((cx - ox) ** 2 + (cy - oy) ** 2 <= near for ox, oy in bodies):
            return cx, cy
        if not bounced:
            px += vx
            py += vy
        if spin is not None:
            _, sx, sw = spin
            if not sx - sw // 4 <= px >> 8 <= sx + sw // 4:
                turns += 1
                if turns <= 2:
                    vx = -vx
                else:
                    spin = None
            if spin is not None:
                vx = (1 if vx >= 0 else -1) * max(abs(vx), TORNADO_VX)
                continue
        vx += ax
        vy += ay
    return None


def safe(hit, target, friends) -> bool:
    """O impacto não pega o bot nem um aliado (friends inclui o bot), salvo quando o alvo está colado neles."""
    return hit is not None and all(math.dist(hit, f) >= SAFE or math.dist(target, f) <= 2 * SAFE for f in friends)


def best_shot(t: Terrain, me: tuple[int, int], target: tuple[int, int], gravity: int, wind: tuple[int, int],
              bodies=(), friends=(), weather=()) -> tuple[int, int, tuple[int, int] | None, int]:
    """(ângulo absoluto, força, impacto, erro em px) que leva o tiro mais perto do alvo sem cair em cima do bot nem
    dos aliados (friends). Entre os que acertam o corpo, prefere o que passa por força/blackforce/elétrico (mais dano):
    o erro deles conta BODY a menos."""
    x, y = me
    tx, ty = target
    aim = (tx, ty - BODY // 2)
    best = None
    for e in ELEVATIONS:
        angle = e if tx >= x else 180 - e

        def score(p):
            crossed = set()
            hit = fly(t, x, y, angle, p, gravity, wind, bodies, weather=weather, crossed=crossed)
            if not safe(hit, target, (me, *friends)):
                return UNSAFE, hit  # fora do mapa ou em cima de si mesmo / de um aliado
            d = math.dist(hit, aim)
            return d - (BODY if d <= BODY and crossed & BOOSTS else 0), hit

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
