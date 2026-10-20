# Tanques (mobiles) e itens

## Tanques

Escolha na sala: 0x3200 = u8 primário + u8 secundário (o secundário só vale no Tag; `0xFF` = aleatório). O servidor
grava os dois em `Game.ClientData[0:2]` e usa como escolha inicial na próxima sala (`room_select_tank.py`).
Índices aceitos: 0..15 e `0xFF` (`TANK_COUNT = 16` em `gunbound/base/enums.py`).

| Imagem | Tanque | Índice |
|:---:|---|---|
| ![Armor](img/tanks/armor.png) | Armor | 0x00 |
| ![Mage](img/tanks/mage.png) | Mage | 0x01 |
| ![Nak](img/tanks/nak.png) | Nak | 0x02 |
| ![Trico](img/tanks/trico.png) | Trico | 0x03 |
| ![BigFoot](img/tanks/bigfoot.png) | BigFoot | 0x04 |
| ![Boomer](img/tanks/boomer.png) | Boomer | 0x05 |
| ![Raon Launcher](img/tanks/raonlauncher.png) | Raon Launcher | 0x06 |
| ![Lightning](img/tanks/lightening.png) | Lightning | 0x07 |
| ![JD](img/tanks/jd.png) | J.D | 0x08 |
| ![A.Sate](img/tanks/a.state.png) | A.Sate | 0x09 |
| ![Ice](img/tanks/ice.png) | Ice | 0x0A |
| ![Turtle](img/tanks/turtle.png) | Turtle | 0x0B |
| ![Grub](img/tanks/grub.png) | Grub | 0x0C |
| ![Aduka](img/tanks/aduka.png) | Aduka | 0x0D |
| ![Kalsiddon](img/tanks/kalsiddon.png) | Kalsiddon | 0x0E |
| ![J.Frog](img/tanks/j.frog.png) | J.Frog | 0x0F |
| ![Dragon](img/tanks/dragon.png) | Dragon | [INCERTO] |
| ![Knight](img/tanks/knight.png) | Knight | [INCERTO] |
| | aleatório | 0xFF |

- Dragon e Knight: emuladores do TH usam 17/18 (14/15 em outra versão); não conferido nos clientes WC. Hoje o
  servidor recusa índice ≥ 16.
- Os mobiles do S2 (Tiburon, Frank, Maya, Phoenix, Wolf, Blue Whale) também não têm índice conferido. **[INCERTO]**
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
