# Capturas do broker original

Log do broker original em modo `-debug` (ver `README.md` de `server/`). Como o broker monta a lista no emulador:
[Lista de servidores.md](Lista%20de%20servidores.md).

## TCP

### 0x1310 → 0x1312 (login)
```
RECV>> [SS=00FAEA10 SQ=35F1 CD=1310] A4 13 02 F4 32 98 A2 CC 6E 85 6C AC 2F 62 80 61 80 B2 2B 36 A2 0A DF A6 1D 47 D9 33 E7 38 5C EB 82 87 54 0D E9 DF 09 08 4C C7 4B 7D BB 3D BD D4 2E 4A 2D 5E D6 E5 28 AA BE B1 6B 60 C5 FA B0 5F
SEND>> [SS=00FAEA10 SQ=CBEB CD=1312 RTC=0000]
```

### 0x1100 → 0x1102 (lista de servidores)
```
RECV>> [SS=00FAEA10 SQ=46A5 CD=1100] 00 00 00 00
SEND>> [SS=00FAEA10 SQ=FF34 CD=1102] 00 00 01 01 00 00 00 10 5B 53 31 5D 20 47 75 6E 62 6F 75 6E 64 20 57 43 16 C1 72 65 61 20 6C 69 76 72 65 5C 6E 53 65 6D 20 61 76 61 74 61 72 7F 00 00 01 20 A8 00 00 00 00 B8 0B 00 01 00 01
```
Um servidor: nome `[S1] Gunbound WC` (u8 16 + texto), descrição `Área livre\nSem avatar` (u8 0x16 + texto),
IP `127.0.0.1`, porta `20 A8` (8360, big-endian); `B8 0B` = 3000, [provável] o máximo de usuários.

## UDP (broker → game server)

### 0xF000 / 0xF001 (status)
```
UDP-RECV [FROM=127.0.0.1:59066 Accept=1] 08 00 00 F0 00 00 00 00
UDP-RECV [FROM=127.0.0.1:8360] 17 00 01 F0 00 00 00 00 00 00 00 00 B8 0B 00 00 00 00 01 00 00 00 00
```
O broker pergunta (0xF000) e o game server responde (0xF001) com o estado dele (o emulador monta em
`gunbound/game/managers/monitor.py`).
