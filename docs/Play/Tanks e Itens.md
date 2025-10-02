| Imagem                                        | Tank Equipado | Código |
|:---------------------------------------------:|---------------|--------|
| ![Armor](./img/tanks/armor.png)               | Armor         | 00 03  |
| ![Mage](./img/tanks/mage.png)                 | Mage          | 01 03  |
| ![Nak](./img/tanks/nak.png)                   | Nak           | 02 03  |
| ![Trico](./img/tanks/trico.png)               | Trico         | 03 03  |
| ![BigFoot](./img/tanks/bigfoot.png)           | BigFoot       | 04 03  |
| ![Boomer](./img/tanks/boomer.png)             | Boomer        | 05 03  |
| ![Raonlauncher](./img/tanks/raonlauncher.png) | Raonlauncher  | 06 03  |
| ![Lightening](./img/tanks/lightening.png)     | Lightening    | 07 03  |
| ![JD](./img/tanks/jd.png/)                    | JD            | 08 03  |
| ![A.Sate](./img/tanks/a.state.png)            | A.Sate        | 09 03  |
| ![Ice](./img/tanks/ice.png)                   | Ice           | 0A 03  |
| ![Turtle](./img/tanks/turtle.png)             | Turtle        | 0B 03  |
| ![Grub](./img/tanks/grub.png)                 | Grub          | 0C 03  |
| ![Aduka](./img/tanks/aduka.png)               | Aduka         | 0D 03  |
| ![Kalsiddon](./img/tanks/kalsiddon.png)       | Kalsiddon     | 0E 03  |
| ![J.Frog](./img/tanks/j.frog.png)             | J.Frog        | 0F 03  |
| ![Random](./img/tanks/random.png)             | Random        | FF 03  |

| Imagem                                          | Itens equipados | Código |
|:-----------------------------------------------:|:----------------|-------:|
| ![Duplo](./img/itens/dual.gif)                  | Duplo           | FF 01  |
| ![Sangue](./img/itens/blood.gif)                | Sangue          | 03     |
| ![Energia 2](./img/itens/energy-2.gif)          | Energia 2       | FF 07  |
| ![Energia 1](./img/itens/energy-1.gif)          | Energia 1       | 07     |
| ![Duplo+](./img/itens/dual+.gif)                | Duplo+          | FF 02  |
| ![Vento Changin](./img/itens/changin-wind.gif)  | Vento Changin   | 0F     |
| ![Team Teleport](./img/itens/team-teleport.gif) | Team Teleport   | FF 0B  |
| ![Bunge Shot](./img/itens/bunge-shot.gif)       | Bunge Shot      | 01     |
| ![Ligar](./img/itens/power-up.gif)              | Ligar           | 02     |
| ![Thunderbolt](./img/itens/thunderbolt.gif)     | Thunderbolt     | FF 06  |
| ![Teleport](./img/itens/teleport.gif)           | Teleport        | FF 0A  |

| ClientData | Bytes | Descrição |
|------------|------:|-------------------------|
| Tank       | 2     | Código do Tank equipado |
| Itens      | 1     | Código do Item, podendo ocupar 2 bytes |
| Itens      | 1     | Código do Item, podendo ocupar 2 bytes |
| Itens      | 1     | Código do Item, podendo ocupar 2 bytes |
| Itens      | 1     | Código do Item, podendo ocupar 2 bytes |
| Itens      | 1     | Código do Item, podendo ocupar 2 bytes |
| Itens      | 1     | Código do Item, podendo ocupar 2 bytes |
| 0x24       | 1     | Desconhecido |
| 0x00       | 91    | Desconhecido |