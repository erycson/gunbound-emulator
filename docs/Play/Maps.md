# Mapas, modos e climas

## Campos da sala (0x2120 criar, 0x3100/0x3101/0x3103 mudar, 0x2103/0x2111 listar)

| Campo | Formato | Valores |
|---|---|---|
| Mapa | u8 | 0 = aleatório, 1..10 (`MAP_COUNT = 11` em `gunbound/base/enums.py`); o 0x3106 do S2 recusa ≥ 11 |
| Settings | u32 | bytes 0-1 fixos `B2 62`; modo = u16 nos bytes 2-3 (`settings >> 16`) |
| Modo | u16 | Solo `0x00`, Score `0x44`, Tag `0x08`, Jewel `0x0C` (`RoomMode`) |
| Capacidade | u8 | 2, 4, 6 ou 8 (1x1 a 4x4) |

Exemplo: settings `B2 62 0C 00` = modo Jewel.

| Mapa | Nº |
|---|---|
| aleatório | 0 |
| Miramo Town | 1 |
| Nirvana | 2 |
| Metropolis | 3 |
| Sea of Hero | 4 |
| Adium Root | 5 |
| Dragon | 6 |
| Cozy Tower | 7 |
| Dummy Slope | 8 |
| Star Dust | 9 |
| Meta Mine | 10 |

## Climas (efeitos do mapa)

Ligados por servidor em `features` no `config.yml` (bits 13..19). O efeito em si roda no cliente; o servidor só manda a
máscara no login. No TH e no S1 o cliente liga os climas por um laço `0x2000 << i`; no S2 (v548/v584) esse laço não foi
achado na análise estática, só o teste próprio do bit 16 [INCERTO]. Os demais bits da máscara: [Eventos.md](../Eventos.md).

| Bit em `features` | Efeito no jogo |
|---|---|
| `EFFECT_FORCE` (13) | faixa que aumenta o dano dos tiros que passam por ela |
| `EFFECT_TORNADO` (14) | faixa que faz o tiro andar em ziguezague |
| `EFFECT_LIGHTNING` (15) | faixa que eletrifica o tiro: ao cair, um raio atinge o chão abaixo |
| `EFFECT_WIND` (16) | [INCERTO] provável "Meteor": muda o vento ao aparecer |
| `EFFECT_THOR` (17) | satélite que atira um laser onde o tiro cai |
| `EFFECT_MOON` (18) | recupera um pouco de vida no início do turno |
| `EFFECT_ECLIPSE` (19) | bloqueia o uso de itens |
