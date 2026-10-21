"""
O que cada mobile tem de especial para o bot, por tiro (1, 2, 'ss'). Índices como em docs/Play/Tanks e Itens.md.
A fase diz quais existem (Phase.tanks + HIDDEN_TANKS); o 0x0D e o 0x0E mudam de mobile do TH para o WC.

Valores são estimativas de jogo para ajustar jogando (docs/Bots.md), não leitura do cliente:
- angles: faixas de ângulo boas (graus); fora delas a penalidade de ângulo cresce até max_pen
- min_dist: alvo mais perto que isso pesa (tiro que precisa de espaço para abrir/andar)
- wind/range: multiplicam o peso do vento e da distância (1 = normal)
- special: trajetória própria; a mira precisa simular o tiro, a tabela só ajusta a chance
"""
from __future__ import annotations
from dataclasses import dataclass, field

FORWARD = ((30, 60),)


@dataclass(frozen=True)
class Shot:
    angles: tuple = FORWARD
    min_dist: float = 0
    max_pen: float = 0.35
    wind: float = 1.0
    range: float = 1.0
    special: bool = False
    note: str = ''


@dataclass(frozen=True)
class Mobile:
    name: str
    shots: dict = field(default_factory=lambda: {1: Shot(), 2: Shot(), 'ss': Shot()})


def mobile(name, s1=Shot(), s2=Shot(), ss=Shot()) -> Mobile:
    return Mobile(name, {1: s1, 2: s2, 'ss': ss})


VERTICAL = ((30, 60), (78, 90))
SPACE = 250

# TH v404: 0x00..0x0F (0x0D Dragon, 0x0E Knight, 0x0F CyberNaK)
TH = {
    0x00: mobile('Armor'),
    0x01: mobile('Mage', Shot(min_dist=SPACE, note='o tiro abre no caminho'), Shot(min_dist=SPACE),
                 Shot(min_dist=SPACE, special=True)),
    0x02: mobile('Nak', s2=Shot(angles=((0, 50),), wind=0.6, special=True, note='tiro 2 cava por baixo da terra')),
    0x03: mobile('Trico', s2=Shot(special=True, note='tiro gira em órbita'), ss=Shot(special=True)),
    0x04: mobile('BigFoot', Shot(range=1.4, note='rajada espalha com a distância'), Shot(range=1.4), Shot(range=1.2)),
    0x05: mobile('Boomer', Shot(angles=VERTICAL, wind=1.6, special=True, note='bumerangue; 89° de perto é normal'),
                 Shot(angles=VERTICAL, wind=1.6, special=True), Shot(angles=VERTICAL, wind=1.4, special=True)),
    0x06: mobile('Raon Launcher', s2=Shot(min_dist=SPACE, special=True, note='minas andam no chão'),
                 ss=Shot(min_dist=SPACE, special=True)),
    0x07: mobile('Lightning', Shot(angles=VERTICAL, note='raio cai na vertical'), Shot(angles=VERTICAL),
                 Shot(angles=VERTICAL, special=True)),
    0x08: mobile('J.D'),
    0x09: mobile('A.Sate', s2=Shot(special=True, note='laser do satélite'), ss=Shot(special=True)),
    0x0A: mobile('Ice', Shot(angles=((30, 72),)), Shot(angles=((30, 72),)), Shot(angles=((30, 72),))),
    0x0B: mobile('Turtle', s2=Shot(range=1.2, special=True, note='divide em bolhas'), ss=Shot(special=True)),
    0x0C: mobile('Grub', s2=Shot(wind=0.7, special=True), ss=Shot(special=True)),
    0x0D: mobile('Dragon', Shot(special=True), Shot(special=True), Shot(special=True)),
    0x0E: mobile('Knight', Shot(special=True), Shot(special=True), Shot(special=True)),
    0x0F: mobile('CyberNaK', s2=Shot(angles=((0, 50),), wind=0.6, special=True)),
}

# WC (v440 em diante): 0x0D Aduka, 0x0E Kalsiddon (precisa de espaço), 0x0F J.Frog; ocultos (só GM) 0x11/0x12,
# que a tabela do cliente (v440 0x5cec3c) troca pelas classes do Dragon e do Knight. 0x10 não é tanque.
WCS1 = {
    **TH,
    0x0D: mobile('Aduka', s2=Shot(special=True), ss=Shot(special=True)),
    0x0E: mobile('Kalsiddon', Shot(min_dist=SPACE), Shot(min_dist=SPACE, special=True),
                 Shot(min_dist=SPACE, special=True)),
    0x0F: mobile('J.Frog', s2=Shot(special=True, note='tiro especial do sapo'), ss=Shot(special=True)),
    0x11: TH[0x0D],
    0x12: TH[0x0E],
}

# S2 (v548/v584): 0x13..0x18; sem estudo ainda, tudo como trajetória própria
WCS2 = {
    **WCS1,
    **{i: mobile(n, Shot(special=True), Shot(special=True), Shot(special=True))
       for i, n in ((0x13, 'Phoenix'), (0x14, 'Maya'), (0x15, 'Wolf'), (0x16, 'Tiburon'), (0x17, 'Blue Whale'),
                    (0x18, 'Frank'))},
}

BY_PHASE = {'TH': TH, 'WCS1': WCS1, 'WCS2': WCS2}


def shot(phase: str, tank: int, kind) -> Shot:
    m = BY_PHASE[phase].get(tank)
    return m.shots[kind] if m else Shot()
