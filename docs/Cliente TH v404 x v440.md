# Cliente TH v404 x v440 (protocolo e itens)

Levantamento feito só por leitura (capstone + REA/Ghidra 12.1.4) no `clientes/TH-v404/Gunbound.gme`
(sha256 `66bae1e8…`, PELock já desempacotado, código na seção `.image`, VA 0x401000–0x5b8400) contra o
`clientes/WC-S1-v440/GunBound.gme` (seção `.unpk`). Endereço sem prefixo = TH; `v440 0x…` = v440.
A fase `TH` em `server/gunbound/game/phase.py` é a base universal: os métodos de `Phase` são os layouts do TH,
e o `WCS1` (v440) sobrescreve o que o WC trouxe.

**Implementado** (itens 1 a 7 do resumo; testes em `tests/test_phase.py::test_th`):
- ProductVersion 0x00628B68 aceito na fase TH.
- Patentes (`grades`) com 2 u16 no 0x1012, 0x2001, 0x200E, 0x2111 e 0x3010; `login_stats` sem CountryRank.
- 0x2105 com 0x19 bytes; 0x2103 sem o byte extra (`list_entry_extra`); 0x6001 sem Recovered (`chest_tail`).
- Kick: o mestre recebe 0x3151 + u8 slot (WC: 0x315F).
- A tabela C→S do TH é o catálogo sem `WC_ONLY` (0x3001, 0x2130, 0x1090, 0x6004, 0x6008, 0x6030, 0x101C).
- Em todas as fases: o Volume do 0x6001 só vai quando o flag "ativo" é 1, e o 0x6021/0x6030 de item sem validade
  não manda mais o u32 extra (os dois desalinhavam o resto do pacote).

Também implementado depois: o 0x1101 no broker e o 0x1102 no layout do TH (13 bytes no fim de cada servidor), na
porta `broker.th_port` ([Lista de servidores.md](Lista%20de%20servidores.md)).

**Não implementado** (falta confirmar): 0x6028 no layout do TH (difere do `ItemGiftRecv`), 0x6005 do TH,
P2P via UDP e o `gunbound/broker/channel_join.py` (cópia antiga que nada importa, ainda com o país).

Legenda: **[INCERTO]** = não confirmado; **[provável]** = deduzido do código, mas sem ver o campo usado na tela.

## Resumo do que muda no servidor (ordem de importância)

| # | O quê | TH | v440 / servidor hoje | Evidência |
|---|---|---|---|---|
| 1 | ProductVersion no 0x1010 | **0x00628B68 (6458216)** | 0x0080F849 (8452169) | `0x44c5a6` / `v440 0x4f2778` |
| 2 | 0x1012: 8 bytes a menos antes do bloco cifrado | bloco cifrado em **+0x51** | +0x59 | `0x44bf1b`–`0x44c150` / `v440 0x4f2168`–`0x4f23b0` |
| 3 | Bloco por jogador do 0x2111/0x3010 | guild 8 + **2 u16** + itens | guild 8 + 4 u16 + itens | lobby `0x4316e9` (Ghidra) e `0x410e20`–`0x410e59` / `v440 0x4103da`–`0x410433` |
| 3b | Usuário no 0x2001 (lista do canal) e no 0x200E (entrou no canal) | guild 8 + **2 u16** | guild 8 + 4 u16 (`ChannelJoinResp`) | 0x2001 `0x4105fd`/`0x41060c` x `v440 0x40faff`–`0x40fb39`; 0x200E `0x41086c`/`0x41087e` x `v440 0x40fd88`–`0x40fdc6` |
| 4 | 0x6001 (baú): registro por item | **sem o byte final** (Recovered) | servidor manda +1 byte | `0x411930`–`0x4119dc` / `v440 0x411180`–`0x411267` |
| 5 | 0x2105 jogador | **0x19 bytes** | 0x1E bytes | lobby `0x430a18` (Ghidra) |
| 6 | 0x2103 entrada da lista | **10 bytes** depois do título (igual ao 0x21F0) | servidor manda 11 (byte extra `in_list`) | lobby `0x4306ef` (Ghidra) |
| 7 | Opcodes que o TH não manda/trata | 0x1090/0x1091, 0x101C/0x101B, 0x2130/0x2131–0x2133, 0x2140/0x2141, 0x3001, 0x6004, 0x6008/0x6009, 0x6030/0x6031, 0x6032, 0x315F, 0x1101 (GP) | | seções 2 e 3 |
| 8 | Opcodes só do TH | C→S 0x6028 (dar item do baú), 0x1101 (no **broker**, implementado); S→C 0x600B, 0x6029, 0x3151 | | seções 2 e 3 |
| — | `login.py`: teste de versão invertido | o TH passa do mesmo jeito que o v440 (ver seção 1); não mexer sozinho | | `login.py` (validação da versão) |

## 1. Transporte, cifra e login

| Item | TH v404 | v440 | Igual? |
|---|---|---|---|
| Função de envio (grava opcode) | `0x4c1510`: opcode em `this+0xA4`, tamanho em `this+0x40A0` | `0x445b40`: `this+0x9C` / `+0x4098` | mesma lógica; só o offset do objeto muda |
| Fechamento/envio | `0x4c16a0` | `0x445cd0` | sim |
| Checksum de envio | `0x4c16ed`: `seq*0x43FD - 0x613D` | `0x445d22` | sim |
| Checksum de recepção | `0x4c1865`: `seq*0x43FD - 0x53FD` | `0x445e8d` | sim |
| Cifra estática (bloco do 0x1010) | `0x4c1580`, tabela de chaves `0x57a448` | `0x445bb0`, tabela `0x5ce138` | **chaves idênticas** (`ffb3b3be…2eb0` x3 e `a9275304…038c`) |
| Cifra com a chave do usuário | `0x4c15f0` (chave em `this+0x80B8`) / decifra `0x4faa90` | `0x445c20` / `0x4b78a0` | sim (AES; S-box em `0x551dd0` / `v440 0x567f88`) |
| S→C cifrados | `0x4c18d4`: 0x1032, 0x1033, 0x201F, 0x3432, 0x4102, 0x4106, 0x4410, 0x6002 (0x6001 só loga) | `0x445ef9`: os mesmos | sim |
| S→C com RTC conferido | `0x4c1a06`: 0x1012 0x1017 0x1031 0x1079 0x1102 0x1312 0x2001 0x2103 0x2111 0x2121 0x2131 0x2132 0x2133 0x6021 **0x6029** | `0x446026`: os mesmos com **0x6031** no lugar de 0x6029 | quase |
| 0x400F recebido | responde 0x2000 com 0xFFFF (`0x4c1a06`→ bloco 0x400F) | igual | sim |
| Entrega às telas | `SendMessageA(hwnd, 0x464, opcode, corpo)` | igual | sim |

### 0x1010 (montado em `0x44c485`–`0x44c5c7`)
Ordem dos campos igual à do v440 (`v440 0x4f2665`–`0x4f2799`):
1. `0x4c1580`: 32 bytes com a chave fixa (usuário 16 + assinatura/sessão 16);
2. 20 bytes (senha), u32 versão do cliente, IP local u32 (`getsockname` do TCP), porta u16 (socket UDP `0x7a3e3c`),
   ProductVersion u32. Os últimos 0x20 bytes são cifrados com a chave do usuário (`0x4c15f0` com `ecx=0x20`).

| Campo | TH | v440 |
|---|---|---|
| Versão do cliente (u32 do bloco 2) | objeto `0x5b60c8` (lido por `0x409ac0`; também aparece nos textos 0x133/0x134 em `0x40cd70`). O `GunBound.ini` do TH tem `Version=404` | objeto `0x5cf1e4` (`0x42bfd0`) |
| **ProductVersion** | **imediato `0x00628B68` = 6458216 em `0x44c5a6`** (o Ghidra mostra como ponteiro; é o mesmo campo do v440) | `0x0080F849` = 8452169 em `v440 0x4f2778` |

- O TH chama `0x409ac0` duas vezes (`0x44c4ec` e `0x44c4f6`) e usa só o segundo resultado. Isso não muda o fio.
- [INCERTO] que o u32 de versão seja 404: não segui o setter do objeto `0x5b60c8`. O candidato é o `Version=404` do ini.
- **Servidor:** feito, 6458216 está em `TH.product_versions`.
- **`login.py` (validação da versão), não é específico do TH:** `0x4c15f0` põe 12 bytes de dado em cada bloco de 16
  (4 de prefixo). A cauda de 34 bytes fica assim: bloco 1 = senha[0:12], bloco 2 = senha[12:20] + versão (em
  `[12:16]`), bloco 3 = IP + porta + ProductVersion. No caminho da senha pura o servidor lê a versão em
  `block_2[8:12]`, que são os bytes 16..19 da senha (zeros numa senha curta). O teste invertido
  (`not is_invalid`) compensa esse offset errado. O layout do TH é igual, então ele passa do mesmo jeito que o v440.
  Se for corrigir, o offset (`[12:16]`) e o teste têm que mudar **juntos**; mudar só o teste quebra o servidor
  v440 com 440..440.
- O 0x2000 automático depois do 0x1012 existe nos dois: `0x44d0f4` / `v440 0x4f2fb4`. `login_ready` continua `None`.

### 0x1012 login ok (leitor na tela de login `0x44bc10`, ramo 0x1012)
Ponteiro de leitura em `0x44bf1b`–`0x44c13d`, comparado com `v440 0x4f2168`–`0x4f239d`. Offsets contados com o RTC u16 em +0:

| Offset TH | Campo TH | Offset v440 / servidor |
|---|---|---|
| +2 u32 | token | +2 |
| +6 [12] | apelido | +6 |
| +0x12 u8 | gênero | +0x12 |
| +0x13 [8] | guild | +0x13 |
| +0x1B u16 | TotalGrade (+5 ao gravar) | +0x1B |
| +0x1D u16 | SeasonGrade (+5) | +0x1D |
| — | **não existe** | +0x1F CountryGrade, +0x21 Country |
| +0x1F u16 | (sem +5) = MemberCount [provável] | +0x23 MemberCount |
| +0x21..+0x3D | **8 u32**, o último é o gold (vai para o objeto `+0x3b730`, o mesmo que o 0x6105 atualiza em `0x4120b4`) | +0x25..+0x45: 9 u32 (TotalRank, SeasonRank, GuildRank, CountryRank, AccumShot, AccumDamage, TotalScore, SeasonScore, Money) |
| +0x41 4×u32 | eventos (lidos só como u16, `0x44c130`) | +0x49 |
| **+0x51** | bloco cifrado (`0x4faa90`, 0x1012) | **+0x59** |

O TH não tem os campos de país: faltam CountryGrade, Country e um u32, provavelmente o CountryRank [provável].
O WC (World Champion) é que trouxe o país, o que bate com o 0x2111/0x3010 (seção 4). Sem a mudança, o bloco cifrado
(features, fatores de score/gold, semente) seria lido 8 bytes antes, e com isso o fator de gold e a semente ficariam errados.

## 2. Opcodes C→S
Levantados pelas chamadas a `0x4c1510` com `push imm` e pelas gravações diretas `mov word [reg+0xA4], imm`
(v440: `0x445b40` e `[reg+0x9C]`).

| | Opcodes |
|---|---|
| Iguais | 0x1000 0x1010 0x1019 0x1020 0x1021 0x1078 0x1100 0x2000 0x2010 0x2100 0x2101 0x2104 0x2110 0x2120 0x3100–0x3104 0x3150 0x3200 0x3210 0x3230 0x3232 0x3430 0x4000 0x4100 0x4104 0x4200 0x4412 0x4500 0x5000 0x5010 0x5100 0x6000 0x600A 0x600E 0x6020 0x6024 0x6100 0x6104 |
| Só no v440 | 0x101C (`v440 0x40eca4`), 0x1090 CLIENT_DATA, 0x2130 quick start, 0x2140/0x2141 GP, **0x3001 sair da sala**, 0x6004 GIFT_MSG, 0x6008 GIFT_CONFIRM, 0x6030 GIFT_BUY |
| Só no TH | **0x6028 ITEM_GIFT** (`0x4d5a1f`, `0x4d5bb4`), **0x1101** (`0x50a7ba`, no socket do **broker** `0x6e3e30`, ao lado do 0x1100 em `0x50a91b`) |

Observações:
- **0x3001:** o TH não tem. Para sair da sala ele manda 0x2000 (há sites na tela da sala, `0x4c2ee7`/`0x4c3f2c`, e nos botões, `0x4c442a`/`0x4c4956`) [provável]. O servidor já tira o jogador da sala na troca de canal.
- **0x1101 no broker:** u16 opcode + até 16 u16 (lista em `0x7a0100`, quantidade em `0x7a00fc`). É a lista de servidores por índice (SPECIFIC_SERVER_LIST), usada na aba dos servidores dos amigos. **Implementado:** o broker responde 0x1102 só com os índices pedidos, na ordem (`server_sorted_list.py`; o original recusa mais de 12 com RTC 7, aqui o limite é 16).
- **0x6028** (`0x4d5a12`–`0x4d5ae2`): `u32 (campo +0x10 do item do baú)` + 16 bytes + 12 bytes (as duas cópias saem do mesmo buffer `ebx`: id e apelido do destinatário [provável]) + u8 tamanho + mensagem. São 0x21 bytes + msg. **Resolvido:** os servidores 2006 e 2007 leem o mesmo layout (u32 chest, Id16, apelido12, u8 len, msg; 2007 asm 0x42eb6d), e o `ItemGiftRecv` (`services.py`) passou a ler assim. O layout antigo do handler (Id16 + chest + 8) era leitura errada. [INCERTO] se o TH cifra esse pacote (`0x4c24a0` só guarda o pacote para reenvio); o servidor original decifra.
- **0x600A** (`0x4da0b3`): u16 qtd + qtd×(u32, u32), igual ao que o servidor espera.

## 3. Opcodes S→C tratados
Fontes: a árvore principal (`0x40f9a6`, contra `v440 0x40e9c9`), o pré-despacho (seção 1) e o switch de cada tela,
varridos para todos os valores.

| Tela / árvore | TH | v440 | Diferença |
|---|---|---|---|
| Principal | `0x40f9a6`: 0x1013 0x1018 0x1022 0x1030 0x1032 0x1040 0x1060 0x1079 0x1FF8 0x1FFA 0x2001 0x200E 0x200F 0x3010 0x3020 0x3400 0x4410 0x4501 0x5001 0x5101 0x6001 0x6005 0x6101 0x6105 | `0x40e9c9`: as mesmas + **0x101B, 0x1091, 0x6032** | o TH não tem 0x101B, 0x1091 e 0x6032 |
| Login `0x44bc10` | 0x1001 0x1012 0x1017 0x101A 0x101F 0x1102 0x2001 0x5001 0x5011–0x5013 | `0x4f1e10`: 0x1001 0x1012 0x1017 0x101F 0x1102 0x2001 | igual no que importa |
| Lobby `0x430680` (switch em `0x4306a5`) | 0x2001 0x201F 0x2103 0x2105 0x2111 0x2121 0x21F0–0x21F7 | `0x4cad8c`: as mesmas + **0x1101 (GP), 0x2131, 0x2132, 0x2133, 0x3010, 0x3432** | sem GP e sem quick start |
| Sala `0x4c2840` (switch em `0x4c284e`) | 0x2001 0x3010 0x3020 0x3105 **0x3151** 0x3201 0x3211 0x3231 0x3233 0x3400 0x3431 0x3432 0x3FFF 0x4410 | `0x4ec50e`: as mesmas com **0x315F** no lugar de 0x3151, e sem 0x4410 | expulsar |
| Jogo `0x4a2ec0` (switch em `0x4a2ee0`) | 0x2001 0x3020 0x3233 0x3400 0x3FFF 0x4102 0x4410 0x4413 (+0x4001–0x4006) | `0x4cfdb1`: as mesmas | igual |
| Loja/avatar `0x4d2290` (switch em `0x4d266f`) | 0x2001 **0x600B** 0x600F 0x6021 0x6025 **0x6029** 0x6101 0x6105 (+0x6002/0x6003/0x6007/0x6008 dentro do 0x6021) | `0x4f3cc4`: 0x2001 **0x6009** 0x600F 0x6021 0x6025 **0x6031** 0x6101 0x6105 | troca de 2 opcodes |

### Sala: 0x3151 x 0x315F, e o P2P
- TH 0x3151 (`0x4c2c23`): RTC u16 = 0 e um byte em +2 (o slot); depois o cliente manda uma mensagem P2P/UDP 0x8200
  (`0x4c2c2d`, objeto UDP `0x7a3e28`). O 0x3201 (`0x4c2baf`, P2P 0x8100) e o 0x3211 (`0x4c2b7e`, P2P 0x8101)
  seguem o mesmo padrão: o TH só lê o RTC e avisa os outros por UDP.
- v440 0x315F (`v440 0x4ec9c3`): lê o slot, compara com o próprio e, se for ele, sai com 0x2000/0xFFFF.
- **Servidor TH (feito, `Phase.kick_ack`):** responder 0x3150 com **0x3151** (RTC 0 + u8 slot) para o mestre e manter o 0x3FFF para o expulso
  (o TH trata 0x3FFF em `0x4c3ef2`). [INCERTO] se o servidor do TH também mandava 0x3020 aos outros: o P2P 0x8200 indica que não precisava.

## 4. Layouts dos pacotes que o servidor manda

| Pacote | TH | v440 / servidor (`room_packets.py`, `phase.py`) | Muda? |
|---|---|---|---|
| 0x1012 | seção 1 | | **sim** |
| 0x2001 | RTC, u16 canal, u8 maior posição, u8 qtd; por usuário: posição, apelido 12, u8, guild 8, **2 u16**; depois o aviso (`0x410501`–`0x41062a`) | `ChannelJoinResp.success`: guild 8 + **4 u16** (`v440 0x40faff`–`0x40fb39`) | **sim: sem CountryGrade/Country** |
| 0x200E | posição, apelido 12, u8, guild 8, **2 u16** (`0x4107cf`–`0x410885`) | `success_update`: 4 u16 (`v440 0x40fd88`–`0x40fdc6`) | **sim** |
| 0x201F | posição u8 em +0, tamanho em +0xD, texto em +0xE (`0x43094a`) | `chat_body` igual | não |
| 0x2103 | RTC, u16 qtd (só o byte baixo é usado), por sala: u16 id, u8 tam (≤0x1E), título, mapa u8, settings u32, **5 bytes** (+5 power, +6 jogadores, +7 máx, +8 estado, +9 senha) = 10 bytes depois do título (`0x4306ef`) | `write_list_entry(in_list=True)` manda 11 (byte extra antes de jogadores) | **sim: sem o byte extra** |
| 0x21F0 | igual à entrada do 0x2103 (10 bytes), `0x430c7c` | `in_list=False` | não |
| 0x2105 | RTC, título pstr, mapa, settings u32, 5 bytes iguais aos do servidor, e por jogador **0x19 bytes**: apelido 12, **1 byte**, guild 8 (+0xD), u32 em +0x15 (TotalGrade+SeasonGrade) (`0x430a18`) | `write_detail_player` 0x1E: apelido 12, gênero, time, guild 8 (+0xE), 4 u16 | **sim** [INCERTO: se o byte em +0xC é o gênero ou o time] |
| 0x2111 | RTC, +2 mestre, +3 eu, +4 u16 sala, pstr título, mapa u8, settings u32, 8 bytes de itens, máx u8, qtd u8; por jogador: slot, apelido 12, gênero, IP/porta ×2, tank1, tank2, time, estado, guild 8, **2 u16 (+5)**, u16 qtd de itens + u32 cada, u8 power; depois o MOTD (`0x4316e9`) | `write_player`: guild 8 + **4 u16** | **sim: sem CountryGrade/Country** |
| 0x3010 | o mesmo bloco por jogador sem o byte de estado: guild, 2 u16, itens (`0x410cda`, u16 em `0x410e20`/`0x410e36`, qtd em `0x410e56`) | v440 4 u16 (`v440 0x4103da`–`0x410430`) | **sim** (mesmo `write_player`) |
| 0x3432 | sequência igual: settings u32, mapa, u16 qtd, por jogador slot/apelido 12/time/tank1/tank2/x/y/turno, u16, seed u32 (`0x4c305d`–`0x4c381b` x `v440 0x4ecee5`–`0x4ed646`) | igual | não. [INCERTO] o v440 lê mais um u16 em `0x4ed6b0`; não achei esse u16 no TH dentro da janela olhada |
| 0x3201/0x3211/0x3151 | só o RTC (o resto vai por P2P) | o servidor manda dados a mais | não quebra |
| 0x6001 | seção 5 | | **sim** |
| 0x6021 | por item: chest u32, item u32, u8, acq u8, flag+[u32], flag+[u32], flag+[u32], **sem byte final** (`0x4d2a96`–`0x4d2b30`) | v440 igual (`v440 0x4f45e8`–`0x4f468c`) | não muda entre versões (ver nota na seção 5) |
| 0x2121, 0x3105, 0x3400, 0x6025 | não conferidos campo a campo | | [INCERTO] |

## 5. Itens, avatar e loja

### Formato do código do item (igual nos dois)
- 0x2111/0x3010 no TH (`0x431a42`, `0x410eb6`): para cada u32, se o código está **fora** de 0x3199A..0x33FFF,
  `slot = (código >> 16) & 0xF` e `índice = código & 0x7FFF`. O bit 0x8000 é ligado quando o jogador é **homem**
  (gênero 0); o slot 3 sempre ganha 0x8000. Dentro da faixa 0x3199A..0x33FFF é item especial: procura na tabela
  (`0x42aa50`) e marca o tipo 1/2 (`+0x44f44`/`+0x44f48`).
- O v440 tem a mesma conta e a mesma faixa (`v440 0x4cbc93`/`0x4cbc9f`), e o código continua
  `(slot << 16) | (homem << 15) | índice` (`tools/xfs_sync`). Os slots são b=0 roupa, h=1 chapéu, g=2 óculos e
  f=3 bandeira/extra. O TH tem `b_store_flag`/`b_store_sortflag`, ou seja, o slot 3 aparece na loja como "flag".
- Tabelas que os dois clientes leem (strings): `Avatar.xfs`, `fb.dat`, `fg.dat`, `fh.dat`, `characterdata.dat` e `ex%d.dat`.
  As imagens são `%cb%05d.img`/`%cg…`/`%ch…` (com a versão `l`).
- **avatar.xfs do TH é outro formato:** começa com `14 06 00 00` seguido de bytes sem cabeçalho zlib. O do v440 começa
  com u32 + `78 9C` (zlib). O `item_sync.py` (XFS2/zlib) não lê o do TH. Os itens do TH precisam de outro leitor ou de uma lista à parte. [INCERTO] o formato (cifrado?).

### 0x6001 baú (leitor `0x4118b9`; v440 `0x411149`)
RTC u16, u16 qtd e, por item:

| Campo | TH | v440 | Servidor hoje (`item.py`) |
|---|---|---|---|
| No u32, Item u32 | sim | sim | sim |
| Wearing u8, Acquisition u8 | sim | sim | sim |
| flag u8 + [u32 validade, mostrada em horas: `/3600` em `0x41196b`] | sim | sim | sim |
| flag u8 + [u32] | sim (`0x41199c`) | sim | "ativo" u8 + Volume u32 só quando ativo = 1 |
| flag u8 + [u32] | sim (`0x4119ba`) | sim | u8 1 + PlaceOrder u32 |
| **u8 final** | **não existe** (depois do 2º flag o TH já usa o código, `0x4119e0`) | sim (`v440 0x41125f`) | Recovered u8 só no WC (`phase.chest_tail`) |

**Servidor TH:** não manda o Recovered (`Phase.chest_tail`). O 0x6021 (compra) já tem o registro sem o byte final
nos dois clientes.

**Corrigido** (valia nas duas versões): o servidor escrevia `u8 0 + u32 0` no 0x6021/0x6009 de item sem validade, e
no 0x6001 mandava o u32 Volume mesmo com o flag "ativo" 0. O cliente pula o u32 quando o flag é 0, então o resto
desalinhava. Hoje o u32 só vai quando o flag é 1 (`item.py`, `item_buy.py`, `item_gift_confirm.py`).

### Loja, presente e avatar
| Função | TH | v440 |
|---|---|---|
| Comprar (0x6020→0x6021), consumir (0x6024→0x6025), vestir (0x600E→0x600F), cash 0x6100→0x6101, gold 0x6104→0x6105 | sim | sim |
| ITEM_LOCATION 0x600A→**0x600B** | manda e trata (`0x4d26a4`) | manda, mas não trata 0x600B |
| Dar item do próprio baú: 0x6028→0x6029 | **sim** | não |
| Comprar presente 0x6030→0x6031, GIFT_MSG 0x6004, GIFT_CONFIRM 0x6008→0x6009 | **não** | sim |
| 0x6005 (mensagem de presente recebida, `0x411fb0`) | u32 + 12 bytes + u32 data (`localtime`) + u8 tam + texto | `v440 0x411017`: u32 + **u32 + u8** + 12 + data + texto (5 bytes a mais) |
| 0x6032 | não | sim |
| Telas | `gMyAvatarDlg`, `gMyAvatarExDlg`, `XPGiftItemDlg`, botões `b_myavatar_gift/sell/dry`, `b_store_*` (cap, cloth, glasse, flag, exitem, setitem) | `XPMyAvatartDlg`, `XPItemBuyDlg`, `XPItemSellDlg`, `XPRecvGiftItemDlg`, `XPSelectItemDlg` |

O avatar e a loja existem no TH. O que falta é o presente comprado (0x6030) e a confirmação de presente
(0x6004/0x6008), que o WC trouxe.

## 6. Outras diferenças
- **Sem Grand Prix:** não há 0x2140/0x2141 no envio, 0x1101 no lobby nem strings `grandprix`/`NS_GRANDPRIXACTIVE`
  (só no v440). O `Phase.check` já recusa `grandprix.enabled` na fase TH.
- **Sem quick start:** o TH não manda 0x2130 e o lobby não trata 0x2131–0x2133, embora o pré-despacho ainda os
  confira (`0x4c1a06`).
- **Sem país:** não tem os campos de país no 0x1012, no 0x2001/0x200E, no 0x2105, no 0x2111 e no 0x3010 (seções 1 e 4).
- **Sem CLIENT_DATA (0x1090/0x1091)** e sem o par 0x101C/0x101B.
- **Mobiles:** os botões vão de `b_ready_mobile01` a `b_ready_mobile15` e as balas de `bullet1` a `bullet16`. O v440 tem
  `bullet17*`/`bullet18*` e `OXPReadyMobile`. O `TANK_COUNT = 16` do servidor serve para o TH. [INCERTO] quais índices
  são válidos (15 botões + aleatório?).
- **Modos:** `b_gamecreate_solo/score/tag/jewel` e `b_ready_1vs1..4vs4`, os mesmos modos do v440.
- **P2P:** no TH as mudanças da sala (tank 0x8100, time 0x8101, expulsar 0x8200) vão por UDP entre os clientes depois do ack do servidor (seção 3).

## Não conferido
- O setter do u32 de versão do 0x1010 (objeto `0x5b60c8`).
- 0x1013, 0x2121, 0x3105, 0x3400, 0x6025 e 0x4102/0x4410/0x4413 campo a campo.
- O comportamento do P2P da sala (0x8100/0x8101/0x8200) quando o UDP cai no túnel TCP.
- O fim do 0x3432 (eco do 0x3430).
- Se o 0x6028 vai cifrado e a ordem que o servidor original lê.
- O formato do `avatar.xfs` do TH.
