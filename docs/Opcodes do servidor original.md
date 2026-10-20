# Opcodes do servidor original (GunBoundServ3.exe, via REA)

Dispatcher em `0x428536` (árvore binária + tabelas de salto). Resposta = opcode + 1 (`0x428040`).
Permissões: `0x427470` = Authority ≥ 98; `0x427490` = Authority ≥ 99. Cada handler registra `Service Request: SVC_*`.
Corpos "cifrados" = blocos de 16 bytes (u32 `cmd - 0x79CE9F82` + 12 de dados), lidos por `decrypt_blocks`.

| Req | SVC | Resp | Onde está aqui | Notas |
|-----|-----|------|----------------|-------|
| 0x1010/0x1011 | LOGIN / ADMIN | 0x1012 | login.py | 0x1011 = mesmo handler (console); recusa banidos |
| 0x1016 | REP_AUTHDWORD | 0x1017 | services.py (comentado) | não implementado: não enviamos desafios |
| 0x1020 | USER_ID | 0x1021.. | misc | |
| 0x1021 | USER_NICK | 0x1022 | services.py | u16 n + n×Id16 → u16 n + n×(Id16+Nick12) |
| 0x1100 | GRANDPRIX_LIST | 0x1101 | grandprix.py | ver [Grand Prix.md](Grand%20Prix.md) |
| 0x2000 | CHANNEL_JOIN | 0x2001 | | |
| 0x2010 | CHAT | 0x2011 | channel_chat.py | também vai aos monitores |
| 0x2020/0x2022 | CHANNEL_MONITOR(_STOP) | 0x2021/0x2023 | admin_console.py | ≥ 98 |
| 0x2100/0x2101 | ROOM_SORTED/SPECIFIC_LIST | | room_sorted_list.py | |
| 0x2104/0x2110/0x2120/0x2130 | DETAIL/JOIN/CREATE/QUICKSTART | | rooms | |
| 0x2140/0x2141 | GRANDPRIX_BEGIN/CANCEL | — | grandprix.py | fila grupo x grupo, sem resposta |
| 0x3001..0x3430 | sala de espera (LEAVE, CHANGE_*, KICK, TANK, TEAM, READY, RETURN_RESULT, START_GAME) | | rooms/game_play | START: 0x3431 só em erro; sucesso = só 0x3432 |
| 0x4000 | PLAY_DROP_USER | 0x400F | services.py | cifrado, byte0 = slot; 0x400F sem corpo ao alvo |
| 0x4100/0x4104/0x4200/0x4412 | DEAD/RESURRECT/END_JEWEL/RESULT | | game_play.py | tetos × fator/100; o 0x4412 do v584 tem outro layout e o servidor responde também 0x4415 (`wcs2/result.py`) |
| 0x4500 | TUNNEL | 0x4501 | game_play.py | u8 n(1..8) + u8 + slots[n] + dados → todos os slots (inclui remetente) |
| 0x5000 | POLICE_ACCUSE | 0x5001 | services.py | Nick16 + u8 len(≤64) + motivo + u16 len(≤0x96A) + anexo → tabela Accuse |
| 0x5010 | BCM | 0x5011 | gm_commands.py | no WCS2, `wcs2/lobby.py` (tipo e cor antes do tamanho; megafone) |
| 0x5100 | COMMAND | 0x5101 | gm_commands.py | ver [Comandos GM.md](Comandos%20GM.md) |
| 0x5110 | CMD_STATUS | 0x5111 | admin_console.py | ≥ 98; layout abaixo |
| 0x5112/0x5114 | CMD_MOTD / CMD_BCM | +1 | admin_console.py | ≥ 98; MOTD u8 alvo (1 canal, 2 sala) + texto |
| 0x5116 | CMD_SETVERSION | +1 | admin_console.py | ≥ 99; estreitar a faixa não responde |
| 0x5120/0x5122 | GRADELIMIT / GUILDLIMIT | +1 | admin_console.py | |
| 0x5124 | FUNCTION_RESTRICT | +1 | admin_console.py | u32 máscara + u32 valor |
| 0x5126 | SET_ALLOWEDGUILD | +1 | admin_console.py | u16 len ≤ 0x4F, senão RTC 0x1B |
| 0x5128 | SET_EVENTACTPROB | +1 | admin_console.py | u16 idx(<4) + u16 prob + u8 + u8; liga bit 0x100000<<idx |
| 0x512A/0x512C | SET_PASSABLE_AUTH / SET_FACTOR | +1 | admin_console.py | FACTOR: u32 score + u32 gold |
| 0x6000..0x6104 | ITEM, GIFT_MSG/CONFIRM, WEAR, BUY, CONSUME, GIFT_BUY, CASH, GOLD | | shop/inventário | 0x600F sem corpo (RTC 0/4) |
| 0x600A | ITEM_LOCATION | 0x600B | services.py | u16 n + n×(chest u32, pos u32), tamanho exato |
| 0x6028 | ITEM_GIFT | 0x6029 | services.py | cifrado: Id16 + chest u32 + 8 **[INVESTIGAR]** + u8 len(≤0x32) + msg |

## Enviados pelo servidor sem pedido

| Opcode | Quando | Onde está aqui |
|---|---|---|
| 0x101F | no 1º UDP com o token do 0x1012, se o IP/porta observados diferem dos declarados no 0x1010 (NAT): u32 ip + u16 porta, ordem de rede (original 0x42b670) | `managers/monitor.py` |
| 0x1050 | presente chegou (UDP admin 0xF020, original 0x42b820), sem corpo | `managers/monitor.py`, `tools/udp_admin.py gift` |
| 0x400F | alvo do 0x4000 (sem corpo) | services.py |

## Layout 0x5111 (STATUS)
u16 usuários, u16 salas, u16 em sala, u16 em canal, u16 grade_min, u16 grade_max, u16 guildlimit, u8 allowedguild,
u32 function_restrict, u8 evento, u32 versão mín, u32 versão máx, u16 nEventos + n×(u16 idx, u16 prob, u8, u8),
u16 passable_auth, u32 score_factor, u32 gold_factor.

## Investigações abertas
- **Grand Prix**: pendências em [Grand Prix.md](Grand%20Prix.md).
- **0x6028**: significado dos 8 bytes após o chest; onde o original grava a mensagem do presente.
- **0x1004 / 0x1019 / 0x101C**: não existem no dispatcher do original; hoje tratados em silêncio.
- **SETVERSION**: o original derruba sessões fora da faixa (`0x40a530`); aqui não.
- **0x1016**: envio dos desafios anti-hack (servidor → cliente) não implementado.
- **SRV desconhecidos**: 0x1032/0x1033, 0x2005/7/8, 0x2012, 0x3007, 0x6002/3/7, 0x6032. O 0x1031 (RTC 0) já é
  mandado na fase WCS2 depois do 0x1012: sem ele o v584 não pede o canal (`phase.WCS2.login_ready`).
- **Botões cinza após o jogo** ("não consegui sair da sala"): aguardando log do console.

## Atualizações da lista de salas no lobby (0x21F0..0x21F7)
O original manda a quem está no canal olhando a lista (0x414890, quem pediu a lista nos últimos 30 s).
Todos começam com u16 id da sala; nenhum é enviado para sala de Grand Prix (flag +0xbd):

| Opcode | Corpo após o id | Onde | Quando |
|---|---|---|---|
| 0x21F0 | entrada igual à do 0x2103: pstr nome, u8 mapa, u32 settings, u8 power user, u8 jogadores, u8 máx, u8 estado, u8 senha | 0x413e60 | sala criada |
| 0x21F1 | — | 0x4145fb | última pessoa saiu |
| 0x21F2 | título cru, sem tamanho nem 00 | 0x416ac3 | troca de título (só aguardando) |
| 0x21F3 | u8 mapa | 0x416777 | troca de mapa (só aguardando) |
| 0x21F4 | u32 settings | 0x416864 | troca de opções/modo (só aguardando) |
| 0x21F5 | u8 nº de jogadores | 0x414266 / 0x41463a | alguém entrou / saiu (sem destruir) |
| 0x21F6 | u8 máx. de jogadores | 0x416994 | troca da capacidade (só aguardando) |
| 0x21F7 | u8 estado | 0x41669d / 0x4199ef | 1 início da partida, 0 fim |

**Implementado** em `RoomManager.notify_lobby` (create/destroy/leave, `Room.start/finish`, `room_join.enter_room`,
`room_settings`). Diferença: vai a todo o lobby do canal (clientes sem sala), não só a quem pediu a lista em 30 s.
O 0x21F5 que mandamos antes do 0x2111 é dessa família. Fim de partida no original: estado 0 + 0x21F7 ao lobby +
0x4413 (sem corpo) a cada jogador; 0x3232 só marca "voltou" e responde 0x3233 RTC 0 (8 se a sala não estiver em jogo).
