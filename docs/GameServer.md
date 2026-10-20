# Capturas do game server original (TCP)

Log do `GunBoundServ3.exe -debug` (ver `README.md` de `server/`). `SQ` = checksum, `CD` = opcode, `RTC` = código
de retorno.

## 0x1000 → 0x1001 (sessão)
```
RECV>> [SS=00BE72D0 SQ=36B1 CD=1000]
SEND>> [SS=00BE72D0 SQ=53E5 CD=1001] 29 00 00 00
```
O u32 da resposta é o token da sessão. Primeiros valores vistos: `0x29` (41), 18467, 6334, 26500, 19169, 15724, 11478,
29358, 26962, 24464, a mesma sequência do `rand()` do MSVC com semente 1. O emulador gera o token em
`gunbound/util/prng.py`. **[INCERTO]** qual dos dois o original usa em cada caso.

## 0x1010 → 0x1012 (login recusado)
```
RECV>> [SS=00BE72D0 SQ=0DAF CD=1010] 5E 10 7D 83 43 10 70 8D BB B2 E5 9E 27 38 0D 94 1A 14 70 8E D2 F6 68 92 24 74 8F 41 65 F3 E1 22 F7 32 F2 CF C2 58 5F 0B D1 18 B9 48 3B D7 C6 80 31 4C 55 AE 68 EE 51 C6 E7 79 C4 38 31 90 1B B7 05 F5 D7 4E 12 F5 1B AF 3E 4C 1C E9 F1 99 EF 46
SEND>> [SS=00BE72D0 SQ=73CD CD=1012 RTC=0004]
```
RTC 4 = usuário sem linha na tabela `Game`.
