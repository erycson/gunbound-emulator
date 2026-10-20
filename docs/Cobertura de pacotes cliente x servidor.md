# Cobertura de pacotes: cliente v440 x servidor

Levantamento feito no `GunBound.gme` v440 limpo (sha256 `9609f7e2…`), só por leitura, com o REA (Ghidra 12.1.4,
evidência `ev_99f506be…`) e um script de varredura com capstone (fora deste repositório).

- **Envio (cliente → servidor):** todo pacote começa em `FUN_00445b40(opcode)`, que grava o opcode em `this+0x9c`. A lista abaixo traz os opcodes passados a essa função, com o endereço da chamada.
- **Recepção (servidor → cliente):** constantes comparadas (`cmp`/`sub`) no dispatch principal (VA `0x445e00–0x446700`) e nos handlers das telas (sala `0x4ec000`, loja `0x4f3000–0x4f4000`, jogo `0x44c000`/`0x4d0000–0x4d1000`).
- **Nomes:** os nomes marcados com "?" vêm da convenção GunBound (RageZone) e não foram confirmados no código.
- **Status completo por opcode e por versão:** [README.md](../README.md#status-por-opcode) e os READMEs
  [TH](../README-TH.md), [S1](../README-WCS1.md), [S2](../README-WCS2.md). Opcodes do S2:
  [Cliente v584 - pacotes.md](Cliente%20v584%20-%20pacotes.md). Dispatcher do original:
  [Opcodes do servidor original.md](Opcodes%20do%20servidor%20original.md).

Legenda da coluna "Servidor": ✅ tratado / enviado · ⛔ não enviado (o original manda, gatilho desconhecido) · — sem uso.

## 0. Regras tiradas do servidor original

Fonte: `server-original/GunBoundServ/GunBoundServ3.exe` (sha256 `f176515f…`, REA/Ghidra; fora deste repositório).

- **Tamanho do corpo de cada pacote C→S** (`FUN_00427b60`): `gunbound/game/protocol/body_rules.py`. O
  `ClientConnection.on_recv` descarta o pacote fora da regra antes do handler, como o original. Layouts que isso confirmou:
  - 0x2100 = 5 bytes, 0x2104 = 2, 0x2110 = 6 (sala u16 + senha[4]), 0x2120 = 10..74.
  - 0x2130 = 0, 0x2140 = 0, 0x3001 = 2.
  - 0x3100 = 1, 0x3101 = 4, **0x3102 = 8** (máscara de itens, os mesmos 8 bytes do 0x2111/0x3400), 0x3103 = 1, **0x3104 = 1..64**.
  - 0x3150 = 1, 0x3200 = 2, 0x3210 = 1, 0x3230 = 1, 0x3232 = 0, 0x3430 ≤ 128.
  - 0x4100 = 5, 0x4104 = 16, 0x4200 = 16, 0x4412 ≥ 32, 0x4500 = 4..522.
  - 0x5010 = 16..272, 0x600E = 7..82, 0x6020/0x6024 = 16.
- **Quick start:** sucesso = **0x2133 com o mesmo corpo do 0x2111** (builder em `0x414436`/`0x414446`, RTC 0). Sem
  sala livre, o original cria `QuickStartRoom` e responde 0x2132; falha = 0x2131 RTC 8.
- **Spawn:** `*_stage_pos.txt` (Rand, Mix e EvsW são idênticos), copiado para `data/stage_pos.txt`. É uma faixa X por
  mapa, lado e vaga, usada no 0x3432 (`gunbound/game/stage_pos.py`).
- **Fatores:** `GoldFactor = 230` e `ScoreFactor = 270`, aplicados ao `config.yml`.

### O que o servidor valida

| Área | Opcodes (C→S → S→C) | Validações |
|---|---|---|
| Lista e detalhe | 0x2100/0x2101 → 0x2103 (6 por página, filtro por modo); 0x2104 → 0x2105 | precisa estar no canal |
| Entrar / quick start | 0x2110 → 0x2111 (+ 0x21F5 ao lobby, 0x3010 aos outros); 0x2130 → 0x2133 / 0x2132 / 0x2131 | sala inexistente, senha errada e em jogo (0x0011); cheia (0x2001); corrida pela última vaga revalidada sob lock |
| Sair | 0x3001, troca de canal 0x2000 (inclusive -1), desconexão → 0x3020 + 0x3400 (novo mestre) | sala vazia é destruída; vencedor recalculado se alguém sai no meio da partida |
| Mestre | 0x3100..0x3104 → 0x3105 ao mestre + 0x3400 aos outros; 0x3150 → 0x3FFF ao expulso + 0x315F (WC) / 0x3151 (TH) ao mestre | só o mestre e só aguardando; capacidade não cai abaixo dos jogadores nem de um slot ocupado; não expulsa GM nem a si mesmo; título até 64 |
| Jogador | 0x3200 → 0x3201; 0x3210 → 0x3211; 0x3230 → 0x3231 | time cheio (metade da capacidade); mestre não usa "pronto"; não troca durante a partida |
| Partida | 0x3430 → 0x3432 (cifrado); 0x4100 → 0x4101 + 0x4102 (+ 0x4410); 0x4104; 0x4200 → 0x4410 após 2 s; 0x4412 → 0x4413 (v584: + 0x4415); 0x3232 → 0x3233; 0x4500 → 0x4501 | iniciar: mestre, ≥ 2 jogadores, todos prontos e times iguais (GM pode jogar sozinho). Morte repetida ignorada. Score com vidas por time e ressurreição. Jewel só no modo Jewel. Resultado processado uma vez, com teto de gold/GP por jogador ([Comandos GM.md](Comandos%20GM.md#multiplicador-goldfactorscorefactor)). Túnel só para a mesma sala, até 1024 bytes |
| GM | 0x5100 → 0x5101; 0x5010 → 0x5101 | só `Authority ≥ 99` ([Comandos GM.md](Comandos%20GM.md)) |
| Avatar | 0x600E → 0x600F | só itens próprios e não vencidos |
| Login | 0x1010 | sessão única: login repetido no mesmo game server derruba a sessão antiga; em outro, é recusado (`CurrentUser`) e a conexão fecha |
| Loja | 0x6020 → 0x6021 | compra sem saldo e menu inexistente recusados sem transação |

Escolhas do emulador, sem fonte: vidas por jogador no Score (`SCORE_LIVES_PER_PLAYER`) e teto de gold/GP por partida
(`MAX_GOLD`, `MAX_GP`). O corpo do 0x600E foi tirado de captura, não do original.

### Itens (`tools/xfs_sync`)

- O `avatar.xfs` é lido (XFS2, zlib) e sincronizado com a tabela `Menu`. O código é `(slot << 16) | (masculino << 15) | índice`, com slot b=0 roupa, h=1 chapéu, g=2 óculos e f=3 extra.
- Uso: `python -I tools/xfs_sync/item_sync.py` (só mostra o plano). Depois, `--apply`, e `--update-prices` para sobrescrever os preços.
- **[INCERTO]** a duração do item no `.xfs` ainda não foi decodificada.

## 1. Login / sessão (GameServer)

| Opcode | Dir | Nome | Servidor | Observação |
|---|---|---|---|---|
| 0x1000 | C→S | GET_SESSION_ID | ✅ | resposta 0x1001 |
| 0x1004 | C→S | ? (enviado por outra rotina, `0x444ba0`) | ✅ silenciado | não existe no original; sem resposta |
| 0x1010 | C→S | LOGIN | ✅ | respostas 0x1012 / 0x1013 / 0x1015 |
| 0x1019 | C→S | ? (`0x40eb95`) | ✅ silenciado | não existe no original |
| 0x101C | C→S | ? (`0x40ec97`) | ✅ silenciado | não existe no original; só WC |
| 0x1020 | C→S | USER_ID | ✅ | |
| 0x1022 | S→C | USER_NICK (resposta) | ✅ | resposta ao 0x1021 (`services.py`) |
| 0x1031 | S→C | ? | ✅ só WCS2 | RTC 0 depois do 0x1012: o v584 só pede o canal depois dele |
| 0x1032/0x1033 | S→C | ? (aviso/kick/desconexão?) | ⛔ | tratados no dispatch |
| 0x1090 | C→S | CLIENT_DATA | ✅ | resposta 0x1091 |
| 0x0000 | C→S | KEEPALIVE | ✅ | sem resposta |

## 2. Broker (lista de servidores)

| Opcode | Dir | Nome | Servidor |
|---|---|---|---|
| 0x1100 | C→S | SORTED_SERVER_LIST | ✅ resposta 0x1102 |
| 0x1101 | C→S (broker, TH) / S→C (game, WC) | SPECIFIC_SERVER_LIST / ranking do Grand Prix | ✅ nos dois: broker do TH ([Lista de servidores.md](Lista%20de%20servidores.md)); no WC o cliente compara 0x1101 em `0x4ca000` (ranking do [Grand Prix](Grand%20Prix.md)) |
| 0x1310 | C→S | LOGIN | ✅ |
| 0x1312 | S→C | LOGIN resp | ✅ |
| 0x3000 / 0x4000 | C→S | GET_MSG / START_GAME | ✅ usados pelo NyxLauncher |
| 0x1311 / 0x1320 / 0x2000 | C→S | game/admin login, setversion | — nenhum cliente manda ao broker |

## 3. Lobby / canal / chat

| Opcode | Dir | Nome | Servidor | Observação |
|---|---|---|---|---|
| 0x2000 | C→S | CHANNEL_JOIN | ✅ | 0x2001 |
| 0x2001 | S→C | CHANNEL_JOIN | ✅ | |
| 0x2005 / 0x2007 / 0x2008 / 0x2012 | S→C | ? (whisper, aviso, lista de usuários?) | ⛔ | tratados no dispatch |
| 0x200E / 0x200F | S→C | entrou/saiu do canal | ✅ | |
| 0x2010 | C→S | CHANNEL_CHAT | ✅ | |
| 0x201F | S→C | CHANNEL_CHAT | ✅ | |
| 0x2031 | S→C | ? | ⛔ | `0x4b1000` |
| 0x21F0..0x21F7 | S→C | lista de salas ao vivo | ✅ | `0x4ca000`; layout em [Opcodes do servidor original.md](Opcodes%20do%20servidor%20original.md) |
| 0x5010 | C→S | BCM | ✅ | GM → 0x5101 a todos ([Comandos GM.md](Comandos%20GM.md)) |
| 0x5001 | S→C | POLICE_ACCUSE (resposta) | ✅ | resposta ao 0x5000 |
| 0x5011 / 0x5013 | S→C | ? | 0x5011 só no v584 (megafone); 0x5013 ⛔ | |
| 0x5100 | C→S | COMMAND | ✅ | resposta 0x5101 |
| 0x5101 | S→C | COMMAND | ✅ | texto cru |

## 4. Salas

| Opcode | Dir | Nome | Servidor | Observação |
|---|---|---|---|---|
| 0x2100 | C→S | ROOM_SORTED_LIST | ✅ | 0x2103 |
| 0x2101 | C→S | ROOM_SPECIFIC_LIST | ✅ | sem layout conhecido; tratado como a lista paginada |
| 0x2104 | C→S | ROOM_DETAIL | ✅ | 0x2105 |
| 0x2110 | C→S | ROOM_JOIN | ✅ | 0x2111 |
| 0x2120 | C→S | ROOM_CREATE | ✅ | 0x2121 |
| 0x2130 | C→S | QUICKSTART | ✅ | 0x2133 / 0x2132 / 0x2131 |
| 0x2140 / 0x2141 | C→S | GRANDPRIX_BEGIN / CANCEL | ✅ | sem resposta |
| 0x3001 | C→S | LEAVE_WAIT_GAMEROOM | ✅ | só WC (o TH sai com 0x2000) |
| 0x3007 | S→C | ? | ⛔ | |
| 0x3010 / 0x3020 | S→C | jogador entrou / saiu | ✅ | |
| 0x3100–0x3104 | C→S | mapa / opção / itens / máx / título | ✅ | resposta 0x3105 |
| 0x3150 | C→S | ROOM_KICK_USER | ✅ | 0x315F (WC) / 0x3151 (TH) + 0x3FFF ao expulso |
| 0x3200 | C→S | SELECT_TANK | ✅ | 0x3201 |
| 0x3210 | C→S | SELECT_TEAM | ✅ | 0x3211 |
| 0x3230 | C→S | USER_READY | ✅ | 0x3231 |
| 0x3232 | C→S | RETURN_RESULT | ✅ | 0x3233 |
| 0x3400 | S→C | novo mestre | ✅ | |
| 0x3430 | C→S | START_GAME | ✅ | sucesso = só 0x3432; 0x3431 só em erro no original |

## 5. Jogo (partida)

| Opcode | Dir | Nome | Servidor | Observação |
|---|---|---|---|---|
| 0x4000 | C→S | PLAY_DROP_USER | ✅ | 0x400F ao alvo |
| 0x4100 | C→S | PLAY_USER_DEAD | ✅ | 0x4101 + 0x4102 |
| 0x4104 | C→S | PLAY_RESURRECT | ✅ | |
| 0x4200 | C→S | PLAY_END_JEWEL | ✅ | vira 0x4410 |
| 0x4001–0x4004 | S→C | eventos de turno/partida | ⛔ | `0x44c000`, `0x4d1000` |
| 0x400F | S→C | derrubado | ✅ | |
| 0x4102 | S→C | morte (cifrado) | ✅ | |
| 0x4106 | S→C | ? (cifrado) | ⛔ | |
| 0x4201–0x4203 | S→C | ? | ⛔ | `0x426000` |
| 0x4410 / 0x4413 | S→C | vencedor / resultado | ✅ | |
| 0x4412 | C→S | PLAY_RESULT | ✅ | |
| 0x4500 / 0x4501 | C→S / S→C | túnel | ✅ | o envio 0x4500 não passa por `0x445b40` |

## 6. Loja / itens / avatar

| Opcode | Dir | Nome | Servidor | Observação |
|---|---|---|---|---|
| 0x6000 | C→S | ITEM | ✅ | 0x6001 |
| 0x6002 / 0x6003 / 0x6007 | S→C | ? | ⛔ | handlers da loja em `0x4f4000` |
| 0x6004 | C→S | GIFT_MSG | ✅ | o cliente não envia por `0x445b40` (outro caminho); no v584 a resposta é 0x6005 |
| 0x6008 | C→S | GIFT_CONFIRM | ✅ | 0x6009 |
| 0x600A | C→S | ITEM_LOCATION | ✅ | 0x600B (o v440 manda, mas não trata o 0x600B) |
| 0x600E | C→S | ITEM_WEAR (salvar avatar) | ✅ | 0x600F |
| 0x6020 | C→S | ITEM_BUY | ✅ | 0x6021; o scan não achou a chamada a `0x445b40` |
| 0x6024 | C→S | ITEM_CONSUME | ✅ | 0x6025 |
| 0x6028 | C→S | ITEM_GIFT | ✅ | 0x6029; o v440 não manda (é do TH) |
| 0x6030 | C→S | ITEM_GIFT_BUY | ✅ | 0x6031 |
| 0x6032 | S→C | 0x6004 | ✅ | aviso de presente aceito/recusado ao remetente (item_gift_msg.py) |
| 0x6100 | C→S | CASH | ✅ | 0x6101 |
| 0x6104 | C→S | GOLD | ✅ | 0x6105 |

## Limitações

- Os nomes com "?" são inferidos e não foram lidos dos handlers.
- O cliente também envia pacotes por outros caminhos (`0x444ba0`, tunnel e relay), por isso a lista de envio pode estar incompleta.
- A recepção foi inferida pelas constantes comparadas; alguns valores podem ser IDs de string e não opcodes.
- Para confirmar o formato (payload) de cada pacote, decompile o handler indicado pelo endereço com o REA (`procedure_pseudo_code`).
- Testes: `python -m unittest tests.test_rooms_shop` e `python -I tools/xfs_sync/test_xfs_sync.py`.
