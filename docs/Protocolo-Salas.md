# Protocolo de salas e partida: GunBound WC v440

Especificação de pesquisa feita em 2026-10-14, **antes** de implementar as salas.

> **Estado atual:** tudo da tabela da seção 4 está implementado. Os formatos que o servidor manda ficam em
> `gunbound/game/room_packets.py` e os handlers em `gunbound/game/protocol/` (`room_*.py`, `game_play.py`).
> Vários layouts marcados aqui como [TH×2]/[INCERTO] foram depois conferidos lendo os clientes e o servidor original
> (REA/Ghidra) e mudam por fase (TH/WCS1/WCS2, `gunbound/game/phase.py`): ver
> [Cliente TH v404 x v440.md](Cliente%20TH%20v404%20x%20v440.md), [Cliente v584 - pacotes.md](Cliente%20v584%20-%20pacotes.md)
> e [Opcodes do servidor original.md](Opcodes%20do%20servidor%20original.md). As notas "Emulador:" abaixo dizem o que
> o servidor faz hoje quando difere da pesquisa.

Escopo: lobby de salas (0x2100 a 0x2121), configuração da sala (0x31xx), tanque, time, pronto, expulsão, saída, início de partida (0x3430/0x3432), eventos de partida (0x41xx a 0x45xx) e notificações.

---

## 1. Resumo

- **Dois bugs (corrigidos):** (a) `room_create.py` lia a capacidade como u8 e comparava com `RoomSize` (0x0200 a 0x0800), então toda criação de sala falhava; (b) `enums.py` tinha 0x3102 e 0x3104 trocados (0x3102 = USEITEM, 0x3104 = TITLE, confirmado por F1, F2 e F3).
- **A maioria dos layouts de sala não tem confirmação WC.** Quase todos vêm de dois emuladores de Thor's Hammer (TH), que concordam entre si mas não necessariamente com o WC v440. Por isso ficam marcados como TH×2 / INCERTO.
- **Turno, tiro e dano não passam pelo TCP.** Nenhuma fonte tem opcode TCP para isso. Os clientes trocam esses dados em UDP (P2P), com IP e porta enviados pelo servidor ao entrar na sala. Existe um túnel TCP (0x4500/0x4501) como fallback.
- **Chat de sala não foi encontrado** em nenhuma fonte. O chat conhecido é o do canal (0x2010/0x201F).
- **Saída da sala:** os dois caminhos existem. O v440 manda 0x3001 (corpo de 2 bytes pela regra do original); o TH não tem 0x3001 e sai com 0x2000 (canal -1). O emulador trata os dois e a desconexão.
- **Divergências entre o código antigo e as fontes TH** (listagem 0x2103, criação 0x2120/0x2121, tanque 0x3200): resolvidas; o emulador segue F3 e o que os clientes confirmaram.
- **Cifragem:** a lista de pacotes cifrados de WC (fonte F4) inclui 0x3432, 0x4102, 0x4104, 0x4200, 0x4410 e 0x4412. Os demais pacotes de sala não aparecem nessa lista.
- **O que falta para fechar WC:** os layouts principais foram conferidos lendo os clientes (v404, v440, v495, v584). Ainda sem captura: o fim do 0x3432 (eco do 0x3430) e campos marcados [INCERTO] nos documentos dos clientes. Ver seção 10.

---

## 2. Convenções

### 2.1 Etiquetas

| Etiqueta | Significado |
|---|---|
| **[WC]** | Confirmado por fonte WC: lista de IDs do ragezone (F1), lista de cifrados WC (F4) ou capturas e docs do projeto (F0: `docs/GameServer.md`, `docs/Play/Tanks e Itens.md`). O código dos handlers de sala não contava, porque na época da pesquisa nunca tinha sido exercitado com salas. |
| **[WC-único]** | Só o plugin v440 (F5) sustenta o item. Precisa de captura. |
| **[TH×2]** | Layout igual em F2 (jglim) e F3 (kyll3r). Ambos são Thor's Hammer. Não verificado em WC: tratar como INCERTO para WC. |
| **[INCERTO]** | Fonte única sem WC, fontes divergentes ou sem fonte. |

### 2.2 Fontes

| ID | Fonte | Versão alvo | Caminho / arquivo |
|---|---|---|---|
| F0 | Código e docs do próprio projeto | WC | `gunbound/game/protocol/*.py`, `gunbound/base/enums.py`, `docs/GameServer.md` (capturas 1000/1010/1012), `docs/Play/Tanks e Itens.md` |
| F1 | Lista de IDs WC (fórum RageZone, thread 1197270: https://forum.ragezone.com/threads/gunbound-wc-packet-identifiers.1197270/). Os nomes foram depois confirmados no binário do original ([Opcodes do servidor original.md](Opcodes%20do%20servidor%20original.md)) | WC | Só nomes e direção, sem layout |
| F2 | jglim/gunbound-server (Python, Thor's Hammer). https://github.com/jglim/gunbound-server | Thor's Hammer | `GunBoundServer/gameserver.py` |
| F3 | kyll3r/GunBound-Java-Server (Java, Thor's Hammer GIS v376 / GBS v404). https://github.com/kyll3r/GunBound-Java-Server | Thor's Hammer | `src/main/java/br/com/gunbound/emulator/gameserver/packets/readers/room/*.java`, `.../room/change/*.java`, `.../room/gameplay/*.java`, `.../packets/writers/RoomWriter.java`, `.../room/GameRoom.java`, `.../room/RoomManager.java`, `.../utils/PacketUtils.java`, `.../OpcodeReaderFactory.java` |
| F4 | CarlosX/GunBoundWC (GunBoundWCEmu, C#). https://github.com/CarlosX/GunBoundWC | WC (só login implementado) | `BrokenServer/BrokenServer/Clases/FunctionOpcode.cs` (`m_CryptedPackets`), `Clases/PacketHandlers.cs` |
| F5 | samuelrizzo/gunbound-v440-functions (plugin do cliente v440). https://github.com/samuelrizzo/gunbound-v440-functions | WC v440 | `dllmain.cpp` (pacote de saída), `ASM/SendPacket.cpp` |
| F6 | thiago-marquezini/GunBoundSvrHook (hook de recv do servidor oficial, WC/S2). https://github.com/thiago-marquezini/GunBoundSvrHook | WC / S2 | `GunBound_ServerRecvHook/dllmain.cpp` (usado só como ferramenta de captura) |
| F7 | garsia0/SnifferGunboundWC (sniffer WC, C#). https://github.com/garsia0/SnifferGunboundWC | WC | `Crypto.cs` (chave estática da GS) |

Fontes vistas e não usadas: Mjolnir, LinBound, GBPirate (sem código de sala lido), colemancda/GunBound (Swift), ThallesLazaro/GunboundTH-Server (Python, Thor's), kyll3r/GunBound-Java (versão anterior de F3).

### 2.3 Notação

- Todos os inteiros são little-endian (LE), salvo onde indicado BE.
- `str[n]`: n bytes, ISO-8859-1 / ASCII, preenchidos com 00 quando fixos.
- Corpo = o que vem depois do cabeçalho de 6 bytes (`len`, `checksum`, `cmd`).

---

## 3. Quadro e cabeçalho

### 3.1 Cabeçalho servidor para cliente

| Offset | Campo | Tipo | Notas |
|---|---|---|---|
| 0 | `len` | u16 LE | Tamanho total = corpo + 6. [F0, F2, F3 concordam] |
| 2 | `checksum` | u16 LE | Ver 3.2. [F0, F2, F3 concordam] |
| 4 | `cmd` | u16 LE | Código do comando |
| 6 | corpo | variável | |

### 3.2 Checksum

Fórmula de F2 e F3 (idêntica à do projeto, `expected_server_checksum`):

```
soma = soma acumulada dos tamanhos de pacotes já enviados (tx_sum)
checksum = ((soma + len) * 0x43FD - 0x53FD) & 0xFFFF
```

O cliente valida a sequência. O projeto calcula o mesmo valor (17405 = 0x43FD, 21501 = 0x53FD). A fórmula do lado cliente para `checksum` de entrada usa outra constante no projeto (`-24893`). **[WC]** na prática: o `on_recv` do projeto descarta todo pacote do cliente cujo checksum não bate, então essa constante já é exercitada por cada pacote de login e de canal. Não há fonte externa para ela.

### 3.3 RTC (u16 logo após o `cmd`)

- F2 e F3 colocam um u16 RTC = 0 logo após o `cmd` em quase todas as respostas de sala. O RTC **não** existe em todas as respostas. Por exemplo, 0x2121, 0x3010 e 0x4101 não têm RTC.
- Em F0, a captura de 0x1012 mostra `RTC=0004` com a mensagem "Usuário não encontrado". Isso indica que o u16 é código de resultado (0 = OK).
- O projeto usa esse u16 como código de status em 0x2121 (`SRV_OK`) e 0x3201 (`SRV_UPDATED`). Emulador: o 0x2103 também leva o RTC antes da contagem, como F2 e F3.

Nota de notação: nas seções abaixo, "RTC" indica o u16 = 0 colocado antes do corpo.

### 3.4 Pacotes cifrados

Lista de F4 (`m_CryptedPackets`), sem indicação de direção: `0x1032, 0x1020, 0x2010, 0x201F, 0x3432, 0x4200, 0x4102, 0x4106, 0x4104, 0x4410, 0x4412`. [WC]

Direção, segundo F2 e F3:

- Cliente para servidor cifrado: 0x2010 (chat do canal), 0x4200, 0x4412, 0x4104 (F3 descriptografa). 0x4100 não aparece como cifrado em F4.
- Servidor para cliente cifrado: 0x201F, 0x3432, 0x4102, 0x4410. 0x4413, 0x3105 e 0x3201 são claros em F2 e F3.
- 0x4106 aparece em F4 sem descrição. [INCERTO]

### 3.5 Cifra e bloco

- F3 completa o corpo até múltiplo de 16 bytes antes de descriptografar 0x4200 e 0x4104 (`paddingLength = 16 - len % 16`). 0x4412 é descriptografado sem esse preenchimento. F2 e F3 preenchem o corpo cifrado de 0x3432 até múltiplo de 12. **[INCERTO]**: o tamanho de bloco (12 ou 16) não está confirmado para WC.
- O emulador (`decrypt_blocks` em `gunbound/game/protocol/base.py`) usa blocos de 16 bytes: 4 de verificação + 12 de dados. A verificação é `cmd - 0x79CE9F82` (mod 2^32), a mesma em todos os cmds cifrados (chat, 0x4104, 0x4200, 0x4412, GM).
- Chave estática de GS (F7 e F0): `FF B3 B3 BE AE 97 AD 83 B9 61 0E 23 A4 3C 2E B0`. A chave dinâmica é derivada do usuário, da senha e do `authToken` (F3, README). Fora do escopo deste documento.

---

## 4. Tabela-resumo de comandos

Legenda de "Recebe": `req` = só quem enviou; `sala` = todos da sala; `outros` = demais da sala; `canal` = canal.

| Cmd | Dir. | Nome | Recebe | Cifrado | Tag | Emulador hoje |
|---|---|---|---|---|---|---|
| 0x2100 | C→S | Pedir lista de salas | | não | [WC] ID (F1) / [TH×2] layout | `room_sorted_list.py`: filtro u8 + início u8 opcional, 6 por página |
| 0x2103 | S→C | Lista de salas | req | não | [TH×2] layout / [INCERTO] WC | `room_packets.room_list`: RTC + layout F3; WC com 1 byte a mais por sala |
| 0x2104 | C→S | Detalhe da sala | | não | [WC] ID (F1) / [TH×2] | `room_join.py` |
| 0x2105 | S→C | Detalhe da sala (resposta) | req | não | [TH×2] | `room_packets.room_detail`; jogador 0x19 (TH) / 0x1E (WC) / 0x22 (v584) bytes |
| 0x2110 | C→S | Entrar na sala | | não | [WC] ID (F1) / [TH×2] | `room_join.py` |
| 0x21F5 | S→C | Pré-aviso de entrada (F2/F3); contagem da sala no original | lobby | não | [TH×2] | é a contagem de jogadores mandada ao lobby (u16 sala + u8), não pré-aviso |
| 0x2111 | S→C | Estado completo da sala ao entrar | req | não | [TH×2] / [INCERTO] WC | `room_packets.join_state` |
| 0x2120 | C→S | Criar sala | | não | [WC] ID (F1) / [TH×2] | `room_create.py` |
| 0x2121 | S→C | Confirmação de criação | req | não | [TH×2] / [INCERTO] WC | `00 00 00` + id + MOTD (F3) |
| 0x2000 | C→S | Trocar de canal (-1 = aleatório). Usado para sair da sala | canal | não | [WC-único] (F5) | `channel_join.py` tira da sala (caminho do TH) |
| 0x3001 | C→S | Sair da sala (WC) | | não | [INCERTO] (F1 só cita) | `room_join.py` (v440; corpo de 2 bytes) |
| 0x3100 | C→S | Trocar mapa (mestre) | req (+0x3105) | não | [WC] ID (F1) / [TH×2] | `room_settings.py`: 0x3105 ao mestre + 0x3400 aos outros |
| 0x3101 | C→S | Trocar opções (mestre) | req (+0x3105) | não | [WC] ID (F1) / [TH×2] | `room_settings.py` |
| 0x3102 | C→S | Usar item (mestre) | req (+0x3105) | não | [WC] ID (F1) / [TH×2] | `room_settings.py`: 8 bytes de máscara de itens (regra do original) |
| 0x3103 | C→S | Capacidade (mestre) | req (+0x3105) | não | [WC] ID (F1) / [TH×2] | `room_settings.py` |
| 0x3104 | C→S | Título (mestre) | req (+0x3105) | não | [WC] ID (F1) / [TH×2] | `room_settings.py`: 1..64 bytes |
| 0x3105 | S→C | Atualização de sala | req / sala (ver 5.5, 5.7) | não | [TH×2] / [INCERTO] WC | RTC só para o mestre |
| 0x3150 | C→S | Expulsar jogador (mestre) | req + 0x3FFF + 0x3020 | não | [WC] ID (F1) / [TH×1] layout | `room_settings.py`: + 0x315F (WC) / 0x3151 + slot (TH) ao mestre |
| 0x3FFF | S→C | Confirmação de expulsão | expulso | não | [TH×1] / [INCERTO] | enviado ao expulso (também no `/close`) |
| 0x3010 | S→C | Entrou um jogador | outros | não | [TH×2] parcial / [INCERTO] | `room_packets.player_joined` |
| 0x3020 | S→C | Jogador saiu (slot u16) | outros | não | [TH×2] / [INCERTO] WC | `room_packets.player_left` |
| 0x3400 | S→C | Migração de host | todos restantes | não | [TH×2] parcial / [INCERTO] | `room_packets.host_change` |
| 0x3200 | C→S | Escolher tanque | req | não | [WC] ID (F1) / [TH×2] layout | `room_select_tank.py`: 2 u8, grava em `ClientData[0:2]` |
| 0x3201 | S→C | Confirmação do tanque | req | não | [TH×2] | RTC |
| 0x3210 | C→S | Escolher time | req + 0x3105 para sala | não | [WC] ID (F1) / [TH×2] | `room_settings.py` (sem 0x3105 à sala) |
| 0x3211 | S→C | Confirmação de time | req | não | [TH×2] | RTC |
| 0x3230 | C→S | Pronto | req | não | [WC] ID (F1) / [TH×2] | `room_settings.py` |
| 0x3231 | S→C | Confirmação de pronto | req | não | [TH×2] | RTC + `00 00` (F3) |
| 0x3430 | C→S | Iniciar partida (mestre) | | não | [WC] ID (F1) / [TH×2] | `game_play.py` |
| 0x3432 | S→C | Dados de início da partida | sala | **sim** [WC] (F4) | [TH×2] layout / [WC] cifrado | `room_packets.game_start`; fim muda no v584 |
| 0x3232 | C→S | Voltar à sala após resultado | req | não | [WC] ID (F1, "MasterOnly") / [TH×2] | `game_play.py` (qualquer jogador) |
| 0x3233 | S→C | Confirmação do retorno | req | não | [TH×2] | RTC |
| 0x4100 | C→S | Morte | req (+0x4101, +0x4102) | não | [WC] ID (F1) / [TH×2] | `game_play.py` |
| 0x4101 | S→C | Confirmação de morte | req | não | [TH×2] | enviado |
| 0x4102 | S→C | Broadcast de morte | sala | **sim** [WC] (F4) | [TH×2] | enviado (layout F3) |
| 0x4104 | C→S | Ressurreição | req | **sim** [WC] (F4) | [WC] ID (F1) / layout [INCERTO] | `game_play.py` (só no Score) |
| 0x4200 | C→S | Fim por jóia (Jewel) | sala (0x4410) | **sim** [WC] (F4) | [WC] ID (F1) / layout [INCERTO] | `game_play.py` (só no Jewel) |
| 0x4410 | S→C | Vencedor / rebroadcast Jewel | sala | **sim** [WC] (F4) | [TH×2] / [INCERTO] WC | enviado |
| 0x4412 | C→S | Resultado da partida | req (+0x4413 para todos) | **sim** [WC] (F4) | [WC] ID (F1) / [TH×2] | `game_play.py`; v584 com outro layout + 0x4415 |
| 0x4413 | S→C | Confirmação do resultado | sala | não | [TH×2] | enviado, sem corpo |
| 0x4500 | C→S | Túnel (fallback UDP) | destino (0x4501) | não | [WC] ID (F1) / layout [INCERTO] | `game_play.py`, layout do original (ver 6.5) |
| 0x4501 | S→C | Encaminhamento do túnel | destino | não | [TH×1] / [INCERTO] WC | enviado |

Não foram encontrados opcodes TCP para turno, tiro, dano ou chat de sala (ver 6.6 e 6.7).

---

## 5. Lobby de salas

### 5.1 0x2100 (C→S) e 0x2103 (S→C): lista de salas

**Requisição 0x2100:** [TH×2] byte 0 do corpo = filtro: 1 = ALL, 2 = WAITING (F2 `data[6]`, F3 `readUnsignedByte`). F3 aceita um segundo byte opcional com o índice inicial da página (0, 6, 12, ...). F3 mostra 6 salas por página (`ROOMS_PER_PAGE = 6`). F2 não pagina e comenta que "client does strange things if more than 6 rooms are sent".

- Emulador: filtro u8 (1 todas, 2 aguardando, 3..6 por modo) + índice inicial u8 opcional, 6 por página. O original aceita 5 bytes de corpo.

**Resposta 0x2103 (F3 `RoomWriter.writeRoomList` + RTC):**

| Campo | Tipo | Notas |
|---|---|---|
| RTC | u16 | 0 (F2 e F3) |
| count | u16 LE | Número de salas na página |
| por sala: `room_id` | u16 LE | Começa em 0 |
| `title_len` + `title` | u8 + str | Título |
| `map` | u8 | 0 = aleatório (F2, F3) |
| `settings` | u32 LE | Ver 5.4 (modo = u16 nos bytes 2-3) |
| `master_pu` | u8 | Flag de power user do mestre (só F3) |
| `players` | u8 | Número de jogadores |
| `capacity` | u8 | Máximo |
| `started` | u8 | 0 aguardando, 1 em jogo |
| `private` | u8 | 1 com senha |
| padding | u8 | 00 ao final da lista (só F3) |

- F2 usa o mesmo layout sem `master_pu` e sem o 00 final. **[TH×2]** no essencial, divergente nos dois campos.
- Emulador: layout de F3 (RTC, `master_pu`, 00 final). O v440 lê **1 byte a mais** entre `master_pu` e `players`; o TH não (`Phase.list_entry_extra`).
- Quem recebe: só o solicitante (`req`). Erro: nenhum.

### 5.2 0x2104 (C→S) e 0x2105 (S→C): detalhe da sala

**Requisição:** `room_id u16 LE` (F2 `data[6:]`, F3 `readShortLE`). [TH×2]. [WC] o ID 0x2104 "SVC_ROOM_DETAIL" está em F1, mas sem direção.

**Resposta 0x2105 (F3 `writeRoomDetail`, com RTC):**

| Campo | Tipo | Notas |
|---|---|---|
| RTC | u16 | 0 |
| `title_len` + `title` | u8 + str | |
| `map` | u8 | |
| `settings` | u32 LE | |
| `master_pu` | u8 | |
| `players` | u8 | |
| `capacity` | u8 | |
| `started` | u8 | |
| `private` | u8 | |
| por jogador: `nick` | str[12] | |
| por jogador: `gender` | u8 | 0 em F3 |
| por jogador: `guild` | str[8] | |
| por jogador: u32 LE | u32 | Valor 1 em F3 (rank comentado) |

- F2 envia, por jogador: `nick[12] + avatar[8] + guild[8] + rank_cur u16 + rank_season u16`, sem gender. **[INCERTO]**: F2 e F3 divergem no bloco por jogador.
- Emulador (conferido nos clientes): TH 0x19 bytes (apelido 12, 1 byte (vai o gênero; [INCERTO] se o TH lê gênero ou time), guild 8, 2 u16); WC 0x1E (apelido 12, gênero, time, guild 8, 4 u16); v584 0x22 (+ u32).
- Sala inexistente: F3 não responde. F2 não valida e responde com valores padrão da classe `Room`. **[INCERTO]**: o comportamento do cliente WC é desconhecido.
- Quem recebe: só o solicitante.

### 5.3 0x2110 (C→S), 0x21F5 e 0x2111 (S→C): entrar na sala

**Requisição 0x2110:**

| Campo | Tipo | Notas |
|---|---|---|
| `room_id` | u16 LE | F2 `data[6:8]`, F3 `readShortLE` |
| `password` | resto | ASCII, terminado em 00. Vazio = sem senha. [TH×2] |

Ramo de sucesso:

1. **0x21F5 (S→C)**, corpo = RTC (u16 0) + `03` (u8). F2 e F3 concordam. [TH×2]. Emulador: o original manda 0x21F5 = u16 sala + u8 nº de jogadores **ao lobby** (lista ao vivo, ver [Opcodes do servidor original.md](Opcodes%20do%20servidor%20original.md)); não é pré-aviso para quem entra.
2. **0x2111 (S→C)**, corpo:

| Campo | Tipo | Notas |
|---|---|---|
| RTC | u16 | 0 |
| `master_slot` | u8 | Slot do mestre (0) |
| `my_slot` | u8 | Slot do solicitante |
| `room_id` | u16 LE | |
| `title_len` + `title` | u8 + str | |
| `map` | u8 | |
| `settings` | u32 LE | |
| `item_state` | u32 LE | F3. F2 manda `FF FF FF FF FF FF FF FF` (8 bytes) no lugar |
| `FF FF FF FF` | 4 bytes | F3 (F2 manda 8 bytes FF) |
| `capacity` | u8 | |
| `players` | u8 | |
| por jogador (ver abaixo) | | |
| MOTD | resto | ISO-8859-1, sem tamanho |

F2 manda `0x0100` (bytes `00 01`) no lugar de `master_slot`/`my_slot`, com o comentário "unknown". Em F3, o mesmo par de bytes vale `[master=0][slot=1]`, o que coincide com o caso de um segundo jogador. É concordância, não confirmação.

Por jogador (F3 `RoomWriter` e `RoomJoinReader`):

| Campo | Tipo |
|---|---|
| `slot` | u8 |
| `nick` | str[12] |
| `gender` | u8 |
| `ip` | 4 bytes (IP do jogador, ordem de rede) |
| `udp_port` | u16 **BE** (F3: 19363 = 0x4BA3) |
| `ip` | 4 bytes (repetido) |
| `udp_port` | u16 **BE** (repetido) |
| `tank_primary` | u8 |
| `tank_secondary` | u8 |
| `team` | u8 |
| `0x01` | u8 |
| `guild` | str[8] |
| `rank_cur` | u16 LE |
| `rank_season` | u16 LE |
| bloco de avatar | se não há itens: `02 00 00 00 00 00 00 00 00 00` (10 bytes). Senão: u8 quantidade, `00`, depois 4 bytes por item (item de 3 bytes LE + `00`) |
| `pu` | u8 (power user) |

F2 manda, por jogador: `slot + name[12] + ip + port + ip + port + tank_p + tank_s + team + avatar[8] + guild[8] + rank_cur u16 + rank_season u16`. Sem gender, sem `0x01`, sem PU, avatar de 8 bytes fixos. **[INCERTO]**: divergência de F2 e F3 no bloco por jogador.

Emulador (`room_packets.write_player`): slot, apelido 12, gênero, IP + porta BE ×2, tank1, tank2, time, **estado**
(1 = presente, 3 = pronto; só no 0x2111), guild 8, patentes (2 u16 no TH, 4 u16 no WC), u16 nº de itens + u32 por item
(10 bytes no v584), u8 power user. Depois do `capacity`/`players` do cabeçalho vem a máscara de itens de 8 bytes
(a mesma do 0x3102).

- **Porta UDP:** F2 usa `20 AB` (8363 em BE, "hardcoded... client listens there for UDP"). F3 usa 19363 (`4B A3`, BE). Emulador: a porta que o cliente informa no login (bloco 3 do 0x1010); 8363 se não houver.
- **Team:** F2 coloca o novo jogador no time com menos jogadores (`find_room_team`). F3 não foi lido nesse ponto. **[TH×1]**.
- **Slot:** o menor livre (F2 `find_room_slot` de 0 a 15; F3 README fala em slots de 0 a 7).

Notificação após a entrada: ver 5.11 (0x3010).

Ramos de erro, só em F3 (**[INCERTO]**):

- Sala inexistente ou senha errada: 0x2111 com corpo `11 00` (u16 0x0011).
- Sala cheia: 0x2111 com corpo `01 20` (u16 0x2001).

F2 não envia erro nenhum (imprime "things are going to break"). F0 usa `SRV_WRONG_VERSION 0x60` e `SRV_WRONG_GENDER 0x2101`, mas não há código de erro de sala confirmado.

Quem recebe: 0x2111 só o solicitante (F2/F3 mandam também o 0x21F5 a ele; o emulador manda o 0x21F5 ao lobby). 0x3010 vai para os outros (ver 5.11).

### 5.4 0x2120 (C→S) e 0x2121 (S→C): criar sala

**Requisição 0x2120 (F2 e F3 concordam no comprimento e na ordem):**

| Campo | Tipo | Notas |
|---|---|---|
| `title_len` | u8 | Emulador aceita 1 a 23 bytes (`RoomOptions.MAX_TITLE`) |
| `title` | str | |
| `settings` | 4 bytes | Ver abaixo |
| `password` | str[4] | 00 = sem senha. F2 usa `string_decode`, F3 `extractString` |
| `capacity` | u8 | 2, 4, 6 ou 8 |

Exemplo de captura de Thor's Hammer, no comentário de F3 (`RoomCreateReader`):

```
24 00 57 2b 20 21 | 14 | 31 32 33 34 35 36 37 38 39 30 41 42 43 44 45 46 47 48 49 4a | b2 62 0c 00 | 31 32 33 34 | 08
 len   checksum cmd  title_len=20  title (20 bytes)                                       settings          senha "1234"  cap=8
```

O total 0x24 = 36 bytes bate com 6 (cabeçalho) + 1 + 20 + 4 + 4 + 1. Isto valida a estrutura da requisição (Thor's). **[TH×2]**.

**Settings (4 bytes):**

- F2 e F3 leem o modo como `settings >> 16` (u16 nos bytes 2 e 3). `B2 62 0C 00` → modo `0x000C` = JEWEL. Valores em F2: `0` = SOLO, `0x44` = SCORE, `0x08` = TAG, `0x0C` = JEWEL.
- Byte 0 = `B2` (fixo, segundo os comentários do projeto e de F3). Byte 1 = `62` (fixo em F2 e F3).
- Emulador: modo = `settings >> 16`, como F2 e F3 (`RoomMode`).

**Resposta 0x2121 (S→C), sem RTC:**

| Campo | Tipo | Notas |
|---|---|---|
| zeros | 3 bytes | F2 e F3: `00 00 00` |
| `room_id` | u16 LE | |
| MOTD | resto | ISO-8859-1, sem tamanho |

- Emulador: `00 00 00 | room_id | MOTD`, como F2 e F3.
- O criador vira mestre no slot 0 (F2 e F3). O projeto também faz `self.conn.room = room` após criar.
- Erro: F3 não responde. F2 não trata. **[INCERTO]**.

Quem recebe: só o criador.

### 5.4.1 0x2130 (C→S): entrada rápida, 0x2133 / 0x2132 / 0x2131 (S→C)

Só WC (o TH não manda). Implementação: `RoomQuickStartRecv` em `gunbound/game/protocol/room_join.py`.
- Há sala livre (`find_quick`, modo do `/qsopt`): entra nela e responde **0x2133**, mesmo corpo do 0x2111.
- Não há: cria a sala `QuickStartRoom` como o original (`0x41a150`/`0x413c30`), com o tamanho do `/qsman` (8 se não for
  tamanho válido), e responde **0x2132**: `u16 rtc 0, u8 slot, u16 room_id, [v584: u8 extra], u8 vagas, pstr título,
  u8 mapa, u32 settings, MOTD`.
- Não conseguiu criar: **0x2131** com RTC 8.

### 5.5 0x3100 a 0x3104 (C→S): alterações do mestre, e 0x3105

**Regra:** só o mestre pode alterar (F3 verifica `room.getRoomMaster().equals(player)`). F2 não verifica. [WC] para o papel "MasterOnly" de 0x3100, 0x3101, 0x3102, 0x3103, 0x3104 em F1.

| Cmd | Campo do corpo | Tipo | Fonte |
|---|---|---|---|
| 0x3100 | `map` (0 = aleatório) | u8 | F2 `data[6]`, F3 `readUnsignedByte` [TH×2] |
| 0x3101 | `settings` | u32 LE (4 bytes) | F2 guarda 4 bytes crus, F3 `readIntLE` [TH×2] |
| 0x3102 | `item_state` | 8 bytes (máscara) | F2 `data[6:8]`, F3 `readShortLE` [TH×2]; o original exige 8 bytes de corpo |
| 0x3103 | `capacity` | u8 | F2 `data[6]`, F3 `readByte` [TH×2] |
| 0x3104 | `title` | str (resto do corpo) | F2 `string_decode`, F3 `stringDecode` [TH×2] |

- Título: ao renomear (0x3104), o original aceita de 1 a 0x40 bytes, mais que os 23 da criação (`RoomOptions.MAX_RENAME`).
- Resposta: 0x3105 só para quem enviou (F2 e F3). Corpo = RTC (2 bytes). **[TH×2]**.
- Efeito colateral: como 0x3105 não vai para os outros, eles não recebem a mudança de mapa, opções, título ou capacidade por este caminho. Emulador: manda 0x3400 (mesmo corpo da troca de mestre) aos outros da sala e 0x21F2..0x21F6 ao lobby.

**0x3105 (S→C), corpo = RTC (2 bytes).** Usado em dois casos: resposta ao mestre (acima) e broadcast para toda a sala após mudança de time (5.7). [TH×2]. **[INCERTO]** no WC: não aparece em F1.

### 5.6 0x3200 (C→S) e 0x3201 (S→C): escolher tanque

**Requisição (F2 e F3 concordam):**

| Campo | Tipo | Notas |
|---|---|---|
| `tank_primary` | u8 | 0xFF = aleatório |
| `tank_secondary` | u8 | Só usado em modo TAG; 0xFF = aleatório |

**Resposta 0x3201:** corpo = RTC (2 bytes), só para quem enviou. [TH×2]

**Índices (F2 `mobile_string`; F3 `Tank.java` não foi lido):**

| Índice | Tanque | Índice | Tanque |
|---|---|---|---|
| 0 | Armor | 9 | A.Sate |
| 1 | Mage | 10 | Ice |
| 2 | Nak | 11 | Turtle |
| 3 | Trico | 12 | Grub |
| 4 | Bigfoot | 13 | Aduka |
| 5 | Boomer | 17 | Dragon (TH) |
| 6 | Raon | 18 | Knight (TH) |
| 7 | Lightning | 255 | Random |
| 8 | J.D. | | |

- F2 comenta que Dragon/Knight são 14/15 em "Serv2" e 17/18 em TH. **[INCERTO]**.
- F0 (`docs/Play/Tanks e Itens.md`) descreve o código como dois bytes `NN 03` (ex.: Armor `00 03`, Mage `01 03`, ..., Kalsiddon `0E 03`, J.Frog `0F 03`, Random `FF 03`). Ou seja, o índice vem primeiro e o `03` é fixo. **[WC]** para esses códigos, em documentação do próprio projeto.
- Emulador: `room_select_tank.py` lê **dois u8** (primário, secundário) e grava em `ClientData[0:2]`; o `NN 03` da doc F0 eram esses dois bytes. O enum `Tank` (`0xNN03`) ficou sem uso.

### 5.7 0x3210 (C→S) e 0x3211 (S→C): escolher time

**Requisição:** `team u8` (0 = A, 1 = B). [TH×2] F3 rejeita 0xFF e desconecta quem não é GM (autoridade < 99). Regra específica do emulador, não confirmada em WC.

**Resposta 0x3211:** corpo = RTC (2 bytes), só para quem enviou. [TH×2]

**Broadcast:** F3 chama `broadcastRoomUpdate()`, que manda **0x3105 (RTC)** para **todos os jogadores da sala**, inclusive quem enviou. F2 não faz broadcast. Emulador: só o 0x3211 (o 0x3105 fazia quem não é mestre reaplicar a sala da própria tela); a troca de time chega aos outros por P2P.

### 5.8 0x3230 (C→S) e 0x3231 (S→C): pronto

**Requisição:** `ready u8` (1 = pronto, 0 = não pronto). F3 lê `== 1`. F2 ignora o valor. [TH×2]

**Resposta 0x3231:**
- F3: RTC + `00 00` (4 bytes no total).
- F2: RTC só (2 bytes no total).
- **[INCERTO]**: comprimento da resposta divergente.

**Estado:** F3 guarda `ready[slot]`. Ao iniciar a partida, todos voltam a "não pronto" (F3 `startGame`). Quem é o mestre não precisa estar pronto (F3 `canStartGame`).

**Broadcast de "pronto" para os outros:** não encontrado. **[INCERTO]**: sem fonte de como o cliente WC vê o estado dos outros.

### 5.9 0x3150 (C→S) e 0x3FFF (S→C): expulsar jogador

**Requisição (F3, [WC] ID em F1, MasterOnly, sem criptografia):** `slot u8`. Só o mestre pode; o alvo precisa ter autoridade < 99.

Emulador: além do 0x3FFF ao expulso e do 0x3020 aos outros, o mestre recebe **0x315F** (WC) ou **0x3151 + u8 slot** (TH).

**Efeito (F3):**
1. Remove o alvo da sala (`roomMngr.handlePlayerLeave`).
2. Envia **0x3FFF** (corpo vazio, sem RTC) ao alvo.
3. Os outros recebem **0x3020** (ver 5.10).

**[INCERTO]**: 0x3FFF também aparece em F2 como resposta do comando de "alive" (0x5100). Pode ser confusão de nomes, não de conteúdo.

### 5.10 Saída da sala e notificações

**Caminhos conhecidos para o cliente sair da sala:**

1. **0x2000 com canal -1 (`FF FF`) [WC-único, F5; mesmo mecanismo em F2].** O plugin v440 de F5 envia `00 20 FF FF` via `SendPacket(&leave, 8)`, o que dá `cmd = 0x2000` com payload `int16 -1`. F2 faz a mesma limpeza em `join_channel`: se `room_slot != -1`, envia 0x3020 e 0x3400 aos demais e remove a sessão da sala. Emulador: `channel_join.py` tira o jogador da sala (é como o TH sai).
2. **0x3001.** F1 cita "SVC_LEAVE_WAIT_GAMEROOM", tipo Public. Confirmado depois: o original exige 2 bytes de corpo e o v440 manda ao sair (o TH não tem). Emulador: tratado em `room_join.py`.
3. **Desconexão.** F2 remove a sessão da sala e manda 0x200F no canal. F3 chama `handlePlayerLeave`, que remove, notifica e elege novo mestre se preciso.

**Notificações ao sair (TH×2, layout consistente):**

**0x3020 (S→C), para os outros da sala.** Corpo: `slot` como **u16 LE**. F2 e F3 concordam. [TH×2]. Quem recebe: os demais da sala. **[INCERTO]** no WC: F1 não lista 0x3020.

**0x3400 (S→C), migração de host.** Enviado a todos que restam, quando o mestre sai. [TH×2 em essência, divergente em detalhes]:

| Campo | Tipo | F3 (`sendHostMigration`) | F2 (`migration_packet`) |
|---|---|---|---|
| novo mestre | u8 | `master_slot` | `slot` do novo dono da chave |
| título | u8 + str | sim | sim |
| mapa | u8 | sim | sim |
| settings | u32 LE | sim | 4 bytes crus |
| item_state | u32 LE | sim | não |
| bytes fixos | 4 (`FF FF FF FF`) | sim | 8 (`FF`×8) |
| capacidade | u8 | sim | sim |

F2 comenta que "if host leaves the room, the packet is never built or sent". **[INCERTO]**: diverge nos bytes fixos e no `item_state`.

### 5.11 0x3010 (S→C): entrou um jogador (notificação aos outros)

Enviado após o 0x2111 do novo jogador. Sem RTC. Layout de F3 (`writeNotifyPlayerJoinedRoom`):

| Campo | Tipo |
|---|---|
| `slot` do novo jogador | u8 |
| `nick` | str[12] |
| `gender` | u8 |
| `ip` | 4 bytes |
| `udp_port` | u16 BE |
| `ip` | 4 bytes |
| `udp_port` | u16 BE |
| `tank_primary` | u8 |
| `tank_secondary` | u8 |
| `team` | u8 |
| `guild` | str[8] |
| `rank_cur` | u16 LE |
| `rank_season` | u16 LE |
| `avatar_count` | u8 |
| `00` | u8 |
| itens de avatar | 4 bytes cada (item 3 bytes LE + 00) |
| `pu` | u8 |

- F3: envia a **todos os outros** da sala.
- F2: envia só ao **host** (`is_room_key`). Layout diferente, sem gender e sem PU. **[INCERTO]**.
- 0x3010 também existe na lista do buddy server em F1 (com outro significado). Não há conflito real, porque são servidores diferentes.

---

## 6. Partida

### 6.1 0x3430 (C→S) e 0x3432 (S→C): iniciar partida

**Requisição 0x3430 (só o mestre, F3 `RoomGameStartReader`):** o corpo é opaco. F2 comenta que os bytes "seem different every time, longer for multiplayer" (ex.: `A2 89 CB 01`), e F3 os devolve no fim de 0x3432. **Tratar o corpo como eco.**

**Condições (F3 `canStartGame`):**
- Com 2 ou mais jogadores: todos os não mestres precisam estar prontos.
- Com 1 jogador: só se o mestre tiver autoridade ≥ 99.

F2 não verifica nada. **[INCERTO]** no WC.

**Resposta 0x3432 (S→C), para todos da sala (inclusive o mestre). Corpo cifrado. Layout em texto claro (F3 `writeGameStartPacket`):**

| Campo | Tipo | Notas |
|---|---|---|
| `settings` | u32 LE | F3. F2 não tem este campo no início |
| `map_em_jogo` | u8 | Se o mapa era 0, sorteado (F2 e F3) |
| `players` | u16 LE | |
| por jogador (22 bytes): `slot` | u8 | |
| `nick` | str[12] | |
| `team` | u8 | |
| `tank_primary` | u8 | Sorteado se 0xFF |
| `tank_secondary` | u8 | |
| `spawn_x` | u16 LE | F3 usa xMin; F2 sorteia entre xMin e xMax |
| `spawn_y` | u16 LE | |
| `turn_order` | u16 LE | Embaralhado |
| marcador de evento | 2 bytes | F3: `FF FF` normal, `00 00` com evento. F2: `00 FF` |
| eco | resto | Bytes recebidos em 0x3430 |
| padding | até múltiplo de 12 | F3 e F2 |

Efeito: a sala muda para "em jogo" (F3 `isGameStarted = true`). A lista de salas passa a mostrar `started = 1`.

**[INCERTO]**: F2 começa o corpo com `map` (u8), seguido de `players` (u16). F3 começa com `settings` (u32), depois `map`. Escolher uma das duas ordens exige captura.

Criptografia: [WC] para o ID 0x3432 cifrado (F4). O corpo claro segue o layout de F3.

Emulador: ordem de F3 (settings, mapa, jogadores), confirmada pelo leitor do v440 e do TH. Depois dos jogadores:
`FF FF` (u16 evento, nenhum) + eco do 0x3430. No v584: u16 evento + 1 byte + eco + 1 byte final (bônus 0x4300).
Posição inicial pela faixa X de `data/stage_pos.txt` (`stage_pos.py`). Sucesso é só o 0x3432; no original o 0x3431 é erro.

### 6.2 0x4100 (C→S), 0x4101 e 0x4102: morte

**Requisição 0x4100 (claro, F3 `GamePlayerDeadReader`):** `cause u8`. F2 comenta o exemplo `13 00 00 00 00`. **[TH×2]** no byte inicial. Significado de `cause` desconhecido. **[INCERTO]**.

**Resposta 0x4101 (S→C, só ao origem):** corpo vazio, sem RTC. F2 e F3 concordam. [TH×2]

**Broadcast 0x4102 (S→C, para toda a sala, cifrado [WC] em F4):** corpo claro de 12 bytes:

```
[slot u8] [13 00 00 00 00 00 00 44 34 47] [team u8]
```

- F3 monta exatamente isso (`buildDeadPlayerPayload`).
- F2 cita nos comentários o broadcast `00130000 00000000 44344700`. Isso bate com o formato acima com `slot=00` e `team=00`. **[TH×2]**.

Após o 4102, F3 verifica fim de partida. Se houver vencedor, manda 0x4410 em 300 ms (ver 6.3). Caso contrário, só o 4102.

**Ressurreição 0x4104 (C→S, cifrado [WC] em F4 e F3 descriptografa):** F3 marca o jogador como vivo. Não há broadcast em F3. Layout do corpo claro: **[INCERTO]**.

### 6.3 0x4410 (S→C) e 0x4200 (C→S): fim de partida

**Vencedor, 0x4410 (S→C, cifrado, sala):** corpo claro de 12 bytes:

```
[winner_team u8] [00 ×11]
```

Enviado quando F3 detecta fim por eliminação (`checkGameEndAndGetWinner`), e só quando há vencedor. **[TH×1]**.

**Divergência:** F2 cita no comentário um 0x4410 com bytes `FF 13 00 00 4B D8 0D F4 4B D8 0D F4`. Não é o mesmo formato. **[INCERTO]**.

**Fim por jóia, 0x4200 (C→S, cifrado [WC] em F4):** F3 descriptografa (preenchendo para 16), espera 2 s e envia **0x4410 cifrado com o mesmo texto claro** para todos da sala, inclusive quem enviou. F2 faz o mesmo rebroadcast. **[TH×2]** no comportamento. Layout do corpo claro: **[INCERTO]**.

### 6.4 0x4412 (C→S), 0x4413 (S→C) e 0x3232 / 0x3233: resultado e retorno

**Requisição 0x4412 (cifrada [WC] em F4, F3 descriptografa). Corpo claro (F3 `GameResultReader`):**

| Campo | Tipo | Notas |
|---|---|---|
| `qtd` | u8 | Número de blocos de jogador |
| por jogador (18 bytes): ignorado | u8 | |
| `slot` | u8 | |
| `gold` | u16 LE | |
| `bonus_gold` | u16 LE | |
| `event_points` | u16 LE | |
| `gp` | u16 LE | |
| `hits` | u16 LE | Acertos |
| ignorado | u16 LE | |
| `damage` | u16 LE | |
| ignorado | u16 LE | |

Bytes restantes são ignorados. F3 também grava as estatísticas no banco (`applyGameResults`) e no log da partida.

**Resposta 0x4413 (S→C, para todos da sala):** corpo vazio, sem RTC, em claro. F2 e F3 concordam. [TH×2]

Após processar o resultado, F3 marca `isGameStarted = false`. A sala volta a "aguardando".

**Retorno 0x3232 (C→S) e 0x3233 (S→C):** o cliente manda 0x3232 e recebe 0x3233 (corpo = RTC, só para o solicitante). F2 também coloca a sala de volta em "aguardando". F3 só confirma. Em F1, 0x3232 é "MasterOnly". F2 e F3 não exigem mestre. **[INCERTO]** sobre quem pode enviar.

### 6.5 0x4500 (C→S) e 0x4501 (S→C): túnel

Fallback quando o UDP entre clientes falha. F2 comenta: "normally tunnel activates when something broke somewhere" e "when blocking the client's udp listen port, the client makes a tunnel request".

**Requisição 0x4500 (F3 `RoomTunnelReader`):**

| Campo | Tipo | Notas |
|---|---|---|
| ignorado | 2 bytes | |
| `dest_slot` | u8 | |
| `data` | resto | Enviado como está |

**Encaminhamento 0x4501 (S→C, ao destino):** corpo = `origin_slot u8` + `data`, sem RTC.

- F3 tenta de novo 3 vezes, com 100 ms entre tentativas. Se falhar tudo, remove o destino da sala e fecha a conexão.
- F2 só imprime e não encaminha. **[INCERTO]**.
- F2 comenta um layout diferente: "first 0xC bytes: metadata? next 0xC bytes: origin, next 0xC bytes: dest". **[INCERTO]**: conflito direto com F3.

**Emulador (layout do servidor original, `0x429f38` / `FUN_00418650`):** `u8 n (1..8)` + `u8` ignorado + `slots[n]`
+ dados. Cada slot listado recebe 0x4501 = `origin_slot u8` + dados, inclusive o próprio remetente (necessário no
jogo solo). Até 1024 bytes de dados.

### 6.6 Turno, tiro e dano

Não há opcode TCP de turno, tiro ou dano em nenhuma fonte (F1 a F4). Os clientes trocam esses dados em **UDP entre si**:

- O servidor manda a cada jogador, em 0x2111 e 0x3010, o IP e a porta UDP dos demais.
- F2 usa porta 8363 (`20 AB`, BE): "client listens there for UDP". F3 usa 19363 (`4B A3`, BE). **[INCERTO]** no WC.
- O túnel 0x4500/0x4501 (6.5) é o fallback TCP.

**Dois clientes no mesmo PC (`local_udp_fix` no game server, padrão `false`).** O cliente v584 abre a UDP 8363
(o agente de RE achou o bind fixo em htons(8363)); o segundo cliente no mesmo PC não consegue essa porta e informa
no login (0x1010) uma porta que não é a dele. Desligado, o servidor repassa no 0x2111/0x3010 a porta informada, o
UDP entre os dois falha e, depois de 5 s sem resposta (v584; 20 s no v440), cada cliente passa a usar o túnel
0x4500 para aquele colega. Ligado, para quem logou de 127.0.0.1 o servidor pergunta ao Windows a porta UDP real do
processo dono da conexão TCP (`gunbound/util/local_udp.py`) e anuncia essa, para o UDP direto funcionar. Já foi
visto, ligado, o P2P não se estabelecer (ping de 250 ms e o mestre ignorando o "pronto"): se isso acontecer, volte a
desligar. Só faz diferença em teste local; jogadores em PCs diferentes não usam.

Consequência para o emulador: **não há o que implementar para turno/tiro em TCP**. Só falta o lobby, a partida (início, morte, fim, resultado) e o fallback.

### 6.7 Chat de sala

Não há opcode de chat de sala em F1 a F4. F1 traz 0x5010 (BCM) e 0x5114 (CMD_BCM), que são mensagens de broadcast, não chat de sala. **[INCERTO]**: se existe chat de sala no WC, não foi encontrado.

O chat de canal existe: 0x2010 (cliente, cifrado) e 0x201F (servidor, cifrado, por canal). Implementado em `channel_chat.py`.

---

## 7. Fluxo completo, em ordem

Cenário: jogador A cria a sala, B entra, escolhem tanque e time, B fica pronto, A inicia, a partida acontece, termina, todos voltam à sala e B sai.

| # | Quem | Pacote | Corpo / efeito | Resposta / broadcast | Tag |
|---|---|---|---|---|---|
| 1 | A | 0x2120 | título, settings, senha, capacidade | 0x2121 para A (A = mestre, slot 0) | [TH×2] layout, [WC] IDs |
| 2 | B | 0x2100 | filtro (1 ALL / 2 WAITING) | 0x2103 para B (lista) | [TH×2] |
| 3 | B | 0x2104 | `room_id` | 0x2105 para B (detalhe) | [TH×2] |
| 4 | B | 0x2110 | `room_id` + senha | F2/F3: 0x21F5 (B), depois 0x2111 (B, estado completo). Emulador: 0x2111 para B, 0x21F5 ao lobby | [TH×2] |
| 5 | srv | 0x3010 | dados de B | para A e demais (TH: só o host) | [TH×2] parcial |
| 6 | B | 0x3200 | tanques primário/secundário | 0x3201 para B | [TH×2] |
| 7 | B | 0x3210 | time | 0x3211 para B; F3 também 0x3105 para todos (o emulador não) | [TH×2] |
| 8 | B | 0x3230 | pronto = 1 | 0x3231 para B | [TH×2] |
| 9 | A | 0x3430 | eco opaco | 0x3432 para todos (cifrado) | [WC] ID, [TH×2] layout |
| 10 | todos | UDP | turnos, tiros, dano | fora do TCP | [INCERTO] porta |
| 11 | X | 0x4100 | `cause` | 0x4101 para X; 0x4102 para todos (cifrado) | [TH×2] |
| 12 | X | 0x4104 | ressurreição (cifrado) | sem broadcast em F3 | [INCERTO] layout |
| 13 | srv | 0x4410 | vencedor (cifrado) | para todos, 300 ms após o fim | [TH×1] |
| 14 | A | 0x4412 | estatísticas (cifrado) | 0x4413 para todos; sala volta a aguardando | [TH×2], [WC] cifrado |
| 15 | cada | 0x3232 | retorno | 0x3233 para quem enviou | [INCERTO] quem pode |
| 16 | B | 0x3001 (WC) ou 0x2000 (-1) (TH) | saída da sala | 0x3020 (slot u16) para os demais; 0x3400 se era o mestre | [WC-único] + [TH×2] |
| 17 | A | 0x3150 (alternativa) | expulsa B | 0x3FFF para B; 0x3020 para os demais | [WC] ID, [TH×1] layout |

Passo 5 é a notificação de entrada, que não é um passo separado do 0x2111: é enviada logo após. Os passos 10 e 11 podem se misturar em tempo real.

---

## 8. Divergências e pontos incertos

Situação depois da implementação. "Emulador" = o que o servidor faz hoje.

| Assunto | Emulador | TH (F2 / F3) | Estado |
|---|---|---|---|
| Ordem de 0x3102 e 0x3104 | 0x3102 = USEITEM, 0x3104 = TITLE | igual (F1, F2, F3) | resolvido |
| Lista de salas, layout | RTC + count + campos u8 + settings 4 bytes + `master_pu` + 00 final; WC +1 byte | RTC + count u16 + campos u8 (+ master_pu e 00 em F3) | resolvido (conferido no TH e no v440) |
| Modo na criação | `settings >> 16` | `settings >> 16` = `0x000C` (JEWEL) | resolvido |
| Capacidade na criação | u8 2/4/6/8 | u8 direto, 2 a 8 | resolvido |
| Valor de JEWEL | `RoomMode.JEWEL = 0x0C` lido de `settings >> 16` (`B2 62 0C 00`) | `0x000C` | resolvido |
| Resposta de criação 0x2121 | `00 00 00 \| id \| MOTD` | `00 00 00 \| id \| MOTD` | resolvido |
| Tanque 0x3200 | dois u8 | dois u8 (primário, secundário) | resolvido |
| Índices de tanque | 0..15 + 0xFF | F2: Dragon/Knight 17/18, F2 cita 14/15 em Serv2. F0: 14 = Kalsiddon | [INCERTO] para Dragon/Knight e mobiles do S2 |
| Lista de salas, paginação | filtro u8 + início u8 opcional, 6 por página | filtro u8, índice inicial opcional, 6 por página (F3) | resolvido |
| Entrada, bloco por jogador | F3 + byte de estado, patentes e itens por fase | F2 e F3 diferem em gender, PU, avatar | resolvido (conferido nos clientes) |
| Porta UDP | a informada no login; 8363 se faltar | 8363 (F2) × 19363 (F3), BE | resolvido |
| Erros de entrada 0x2111 | `11 00` e `01 20` (F3) | F3: `11 00` e `01 20`. F2: sem erro | [INCERTO] sem captura |
| Ready 0x3231 | 4 bytes (F3) | F3: 4 bytes. F2: 2 bytes | [INCERTO] sem captura |
| Ready broadcast | nenhum; o estado vai no 0x2111 (3 = pronto) | não encontrado | [INCERTO] |
| 0x3010 para quem | todos os outros da sala | F3: todos. F2: só host | resolvido |
| 0x3400 bytes fixos | 8 bytes de máscara de itens | F3: 4 bytes `FF`. F2: 8 bytes `FF` | resolvido pela regra do 0x3102 (8 bytes) |
| 0x3432 ordem inicial | settings, mapa, jogadores (F3) | F2: map, depois players. F3: settings, map, players | resolvido (leitor do v440 e do TH) |
| 0x3432 padding | cifra em blocos de 16 (4 de prefixo + 12 de dados) | F2 e F3: 12. F3 descriptografa 0x4200 com 16 | resolvido |
| Mestre em 0x3232 | qualquer jogador | F1: MasterOnly. F2 e F3: qualquer um | [INCERTO] |
| 0x4410 bytes | F3: `[team][00×11]`; no Jewel, eco do 0x4200 | F3: `[team][00×11]`. F2 cita `FF 13 00 00 4B D8 ...` | [INCERTO] |
| 0x4500 layout | layout do original (6.5) | F2 (comentário): 3×12 bytes. F3: 2 + dest u8 | resolvido |
| 0x3FFF | expulsão (0x3150 e `/close`) | F3: expulsão. F2: resposta de "alive" (0x5100) | resolvido |
| Saída da sala | 0x3001 (WC), 0x2000 (TH) e desconexão | F5: 0x2000 com -1. F1: 0x3001 | resolvido |
| Atualização de mapa/opções para outros | 0x3400 aos outros + 0x21F2..0x21F6 ao lobby | só ao mestre (0x3105) | resolvido |
| Chat de sala | não existe | não encontrado | [INCERTO] |
| Turno/tiro em TCP | não existe | não existe (UDP) | Achado. Não implementar em TCP |
| Verificação do cifrado (novos cmds) | `cmd - 0x79CE9F82` em todos (`decrypt_blocks`) | não examinado | em uso |

---

## 9. Observações sobre o código (resolvidas)

Problemas achados durante a pesquisa, todos corrigidos depois:

- `enums.py`: 0x3102 e 0x3104 trocados.
- `RoomSize` (0x0200 a 0x0800) contra a capacidade u8 do 0x2120: toda criação de sala falhava.
- `room_create.py`: `RoomMap(read_uint16())` sobre os bytes de modo.
- `room_sorted_list.py`: classe com nome copiado de outro arquivo e resposta sem RTC.
- `channel_join.py`: a troca de canal não tirava o jogador da sala; `channel_full()` era chamado sem `conn`.
- Handlers e enums que faltavam para 0x2104..0x4501.

---

## 10. Como validar os INCERTOs

Os itens 1 a 4 e 7 já foram conferidos lendo os clientes (ver o "Estado atual" no topo). Ainda valem capturas para 5 e 6.

Ordem sugerida, da mais valiosa para a menos:

1. **0x2120 e 0x2121.** Criar sala com título, senha e capacidade conhecidos. Confirma o layout da requisição, a posição do id na resposta e o modo (`B2 62 0C 00` ou `B2 0C 62 00`).
2. **0x2103.** Com uma sala criada, pedir a lista com o cliente. Confirma se há RTC e a largura dos campos.
3. **0x2110 e 0x2111.** Entrar com um segundo cliente. Confirma o bloco por jogador, a porta UDP e os erros.
4. **0x3200 e 0x3201.** Trocar tanques e comparar os bytes com a tabela de [Play/Tanks e Itens.md](Play/Tanks%20e%20Itens.md).
5. **0x3430 e 0x3432.** Iniciar a partida e descriptografar o 0x3432 (ver ferramentas abaixo).
6. **0x4412 e 0x4413.** Terminar uma partida e capturar o resultado descriptografado.
7. **0x2000 com -1 e 0x3001.** Sair da sala pelo cliente e capturar qual pacote é enviado.

Ferramentas:

- **F7 (`garsia0/SnifferGunboundWC`):** captura e descriptografa pacotes WC. Já tem a chave estática da GS e o `Crypto.cs` para a cifra dinâmica.
- **F6 (`thiago-marquezini/GunBoundSvrHook`):** hook de `recv()` do servidor oficial. Só para ver o que o servidor oficial recebe. Foi testado com o servidor WC/S2. Requer ajuste de endereços.
- **Servidor oficial com `-debug`**, para comparar o tráfego real.
- **F5 (`gunbound-v440-functions`):** referência de como o cliente v440 monta e envia pacotes (`SendPacket` em `0x00445CD0`). Útil para enviar pacotes de teste ao servidor do projeto, sem alterar o servidor.

---

## 11. Limitações

- Quase toda a especificação de layout vem de Thor's Hammer. Só os IDs e alguns comportamentos têm fonte WC. A tabela da seção 4 deixa isso explícito.
- A lista de IDs do RageZone (F1) não pôde ser lida ao vivo (403); usou-se uma cópia, só com nomes e direção. Os nomes foram depois conferidos no binário do original.
- Não foram lidos Mjolnir, LinBound, GBPirate, colemancda/GunBound e ThallesLazaro/GunboundTH-Server. Podem confirmar ou contradizer partes deste documento.
- Não foi baixado nem executado nenhum binário de terceiros. Os trechos de código foram lidos apenas para extrair layouts.
