# Tanques (mobiles) e itens

## Tanques

Escolha na sala: 0x3200 = u8 primário + u8 secundário (o secundário só vale no Tag; `0xFF` = aleatório). O servidor
grava os dois em `Game.ClientData[0:2]` e usa como escolha inicial na próxima sala (`room_select_tank.py`).
No 0x3432 os dois saem sorteados, mesmo fora do Tag: o v440 e o v584 indexam a tabela de tanques com o secundário, e
`0xFF` lê fora dela.
Índices aceitos: os que a fábrica de personagens do cliente da fase desenha (`Phase.tanks` em `gunbound/game/phase.py`)
e `0xFF`. Os ocultos `0x11`/`0x12` (`HIDDEN_TANKS`) só para Authority ≥ 98, como o servidor 2007 (0x42d048).

**No WC o byte do fio não é a classe.** O cliente troca o byte por uma tabela antes da fábrica (v440 `0x5cec3c`, v495
igual, v584 `0x679160`): 0..12 iguais, 0x0D → 15, 0x0E → 16, 0x0F → 17, 0x11 → 13 (Dragon), 0x12 → 14 (Knight) e
0x10 → 18 no S1 (não existe, cai no Armor) ou −1 no v584. O v584 passa 0x13 em diante sem troca (`0x4198c0`). O TH não
tem tabela. Por isso o 0x10 não é aceito em nenhuma fase, e os ocultos do WC (0x11/0x12) são o Dragon e o Knight.
A tabela abaixo é o índice **da fábrica**; no WC, a linha que vale para o byte do fio é a de `tabela[byte]`.

Índices conferidos no switch da fábrica de cada cliente (leitura estática; classe = nome RTTI do cliente):

| Imagem | Tanque (nome de tela) | Índice | Classe no cliente | TH v404 | S1 v440/v495 | S2 v584 |
|:---:|---|---|---|:---:|:---:|:---:|
| ![Armor](img/tanks/armor.png) | Armor | 0x00 | Armortank | ✓ | ✓ | ✓ |
| ![Mage](img/tanks/mage.png) | Mage | 0x01 | Magetank | ✓ | ✓ | ✓ |
| ![Nak](img/tanks/nak.png) | Nak | 0x02 | NaKtank | ✓ | ✓ | ✓ |
| ![Trico](img/tanks/trico.png) | Trico | 0x03 | Woodtank | ✓ | ✓ | ✓ |
| ![BigFoot](img/tanks/bigfoot.png) | BigFoot | 0x04 | Multitank | ✓ | ✓ | ✓ |
| ![Boomer](img/tanks/boomer.png) | Boomer | 0x05 | Boomertank | ✓ | ✓ | ✓ |
| ![Raon Launcher](img/tanks/raonlauncher.png) | Raon Launcher | 0x06 | Rayontank | ✓ | ✓ | ✓ |
| ![Lightning](img/tanks/lightening.png) | Lightning | 0x07 | Lightningtank | ✓ | ✓ | ✓ |
| ![JD](img/tanks/jd.png) | J.D | 0x08 | Crystaltank | ✓ | ✓ | ✓ |
| ![A.Sate](img/tanks/a.state.png) | A.Sate | 0x09 | Laser | ✓ | ✓ | ✓ |
| ![Ice](img/tanks/ice.png) | Ice | 0x0A | Icetank | ✓ | ✓ | ✓ |
| ![Turtle](img/tanks/turtle.png) | Turtle | 0x0B | Turtletank | ✓ | ✓ | ✓ |
| ![Grub](img/tanks/grub.png) | Grub | 0x0C | Grubtank | ✓ | ✓ | ✓ |
| ![Dragon](img/tanks/dragon.png) ![Aduka](img/tanks/aduka.png) | TH: Dragon · WC: Aduka [INCERTO] | 0x0D | Dragontank | ✓ | ✓ | ✓ |
| ![Knight](img/tanks/knight.png) ![Kalsiddon](img/tanks/kalsiddon.png) | TH: Knight · WC: Kalsiddon [INCERTO] | 0x0E | Knight | ✓ | ✓ | ✓ |
| ![J.Frog](img/tanks/j.frog.png) | WC: J.Frog [INCERTO] | 0x0F | CyberNaKtank | ✓ | ✓ | ✓ |
| | [INCERTO] | 0x10 | BigFootMarkII | – | ✓ | ✓ |
| | oculto (GM) | 0x11 | Frog | – | ✓ | ✓ |
| | oculto (GM) | 0x12 | não existe: cai no Armor | – | – | – |
| | Phoenix | 0x13 | Phoenix | – | – | ✓ |
| | Maya | 0x14 | Maya | – | – | ✓ |
| | Wolf | 0x15 | Wolf | – | – | ✓ |
| | Tiburon | 0x16 | Tiburon | – | – | ✓ |
| | Blue Whale | 0x17 | BlueWhale | – | – | ✓ |
| | Frank | 0x18 | Frank | – | – | ✓ |
| | aleatório | 0xFF | | ✓ | ✓ | ✓ |

- Fábricas: TH 0x434d30 (0..0xF), v440 0x42e5d0 e v495 0x430b80 (0..0x11), dump do v584 0x4427c0 (0..0x11 e
  0x13..0x18). O TH desenha o Dragon (0x0D) e o Knight (0x0E) como mobiles normais; no WC as mesmas classes ficam
  nesses índices, mas o nome de tela do WC (Aduka/Kalsiddon/J.Frog) vem da versão antiga deste arquivo e não foi
  conferido no texto do cliente.
- Aleatório (`0xFF`): o original 2006/2007 sorteia `rand&0xF` (0..15) e, com `Tank.Hidden.Ratio`, um oculto
  0x11/0x12. O S2 não tem servidor original: sorteia todos os índices não ocultos do v584 (`WCS2.random_tanks`).
- Versões antigas deste arquivo mostravam o código como `NN 03` (o enum `Tank` ainda tem esses valores). Eram os 2
  primeiros bytes do `ClientData` lidos juntos: primário `NN` e [provável] secundário 3 na captura. O servidor trata
  como dois u8.

## Itens de batalha

Códigos dos itens equipados, como aparecem no `ClientData` depois dos tanques (captura do v440). Item de 2 espaços
ocupa 2 bytes (`FF` + código).

| Imagem | Item | Código |
|:---:|---|---|
| ![Dual](img/itens/dual.gif) | Dual | `FF 01` |
| ![Dual+](img/itens/dual+.gif) | Dual+ | `FF 02` |
| ![Blood](img/itens/blood.gif) | Blood | `03` |
| ![Energy 1](img/itens/energy-1.gif) | Energy 1 | `07` |
| ![Energy 2](img/itens/energy-2.gif) | Energy 2 | `FF 07` |
| ![Change Wind](img/itens/changin-wind.gif) | Change Wind | `0F` |
| ![Team Teleport](img/itens/team-teleport.gif) | Team Teleport | `FF 0B` |
| ![Bunge Shot](img/itens/bunge-shot.gif) | Bunge Shot | `01` |
| ![Power Up](img/itens/power-up.gif) | Power Up | `02` |
| ![Thunderbolt](img/itens/thunderbolt.gif) | Thunderbolt | `FF 06` |
| ![Teleport](img/itens/teleport.gif) | Teleport | `FF 0A` |

## `Game.ClientData` (captura do v440)

| Bytes | Conteúdo |
|---:|---|
| 2 | tanque primário e secundário |
| 6 × 1 | itens (um item de 2 espaços ocupa 2 bytes) |
| 1 | `0x24` [INCERTO] |
| 91 | `0x00` [INCERTO] |
