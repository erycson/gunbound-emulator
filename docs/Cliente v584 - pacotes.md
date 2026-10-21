# Cliente v584 (WC S2): pacotes

Levantamento feito no dump desempacotado do `GunBound.gme` do v584 (sha256 `a0ba7802…`), só por leitura, com REA
(Ghidra 12.1.4) e capstone. Comparado com o v440 e com `gunbound/game/protocol/enums.py` (servidor modelado no
GunBoundServ3 / cliente v440). No emulador o v584 é a fase **WCS2** (`gunbound/game/phase.py`); status por opcode em
[README-WCS2.md](../README-WCS2.md).

## Como o cliente monta e recebe pacotes
- **Envio:** opcode gravado em `socket+0x94` (`FUN_004558c0(opcode)` ou `mov word [reg+0x94], opcode` embutido). No v440 era `FUN_00445b40`, `+0x9C`. São 78 opcodes distintos.
- **Recepção:** a camada de socket `FUN_00455c10` confere checksum, decifra 0x1032, 0x1033, 0x201F, 0x3432, 0x4102, 0x4106, 0x4410 e 0x6002 e manda o opcode por `PostMessage(0x464)`.
  Primeiro trata o handler global `FUN_0040F740`, depois a tela atual pelo slot 1 da vtable:
  ServerMode `0x5141C0`, GameListMode `0x4D5760`, ReadyMode `0x508820`, PlayMode `0x4DBFC0`, ShopMode `0x516500`.
  Os pacotes 0x8xxx de PlayMode e ReadyMode (`0x4DD8A0` e `0x50AFE0`) são P2P/UDP entre clientes, não vêm do servidor.
- Cuidado: em vários handlers, os valores 0x5001..0x5014, 0x6020, 0x7000..0x7008 e 0x8000..0x8003 são **código de retorno (RTC)**, não opcode.
- Opcode desconhecido não derruba o cliente (confirmado no v440, `FUN_00445D70`: cai no `default` e só é repassado à
  tela; só o 0x1FFF desconecta). Pacote a mais não quebra versão antiga; mudar o corpo de um opcode existente quebra.

## Conclusão
- **O núcleo é o mesmo do v440:** 0x1010 login, 0x1020/0x1021, 0x1090, 0x2000/0x2010, 0x21xx salas, 0x30xx-0x32xx sala de espera,
  0x3430 início, 0x4100/0x4104/0x4200/0x4412/0x4500 partida, 0x5010/0x5100, 0x6000-0x6024 loja, 0x6100/0x6104 cash/gold, 0x1100/0x2140/0x2141 Grand Prix.
- **O cliente não envia:** 0x4000 (drop), 0x5000 (denúncia), 0x6028 (gift), 0x600A (location), keepalive 0x0000 nem os comandos de console 0x511x/0x512x (do console admin, não do cliente).
  [INVESTIGAR] Esses quatro opcodes do cliente não foram achados com imediato; podem ter sido removidos ou sair por um caminho cifrado diferente.
- **O que muda é acréscimo:** 33 opcodes novos de envio e cerca de 70 de recepção, todos de sistemas que o v440 não tem.
  O GunBoundServ3 original também não tem nenhum deles (ver [Opcodes do servidor original.md](Opcodes%20do%20servidor%20original.md)).
- **Layouts que mudaram** em opcodes comuns: 0x1010, 0x201F, 0x2105, 0x2111/0x3010, 0x3432, 0x4412, 0x5010, 0x1101 (seção "Layout dos pacotes comuns").

## Opcodes novos que o cliente ENVIA (C→S)
Confiança: A = janela e strings confirmam · M = provável · B = só indício. "Aqui" = arquivo em `gunbound/game/protocol/wcs2/`.

| Opcode | Resposta | Janela / contexto | Para que serve | Conf. | Aqui |
|---|---|---|---|---|---|
| 0x1078 | 0x1079 | ErrorCodeDialog `0x4d3820` | OK do aviso de e-mail não verificado (0x1060); 0x1079 RTC 0 mostra o texto 270 | A | events.py |
| 0x3106 | 0x3107 | sala (slot, modo, opção) | mudar a configuração inteira da sala | M | room.py |
| 0x3433 | — | carregamento `0x559953` | host avisa fim do carregamento; o cliente não espera resposta | B | events.py (só silencia) |
| 0x3450 | 0x3451 | XPReadyInviteDlg | lista para convidar à sala | A | lobby.py |
| 0x3452 | — (0x2025 ao convidado) | sala, editbox | convite: sala, senha, msg, apelido | A | lobby.py |
| 0x4300 | — | partida, "+%dGold, +%dGP" | bônus da partida (tipo sorteado no 0x3432) | A | bonus.py |
| 0x4520 | 0x4410 | canal Stage | fim de missão Stage (meta ou tempo); o servidor responde com o vencedor | M | bonus.py |
| 0x6050 | 0x6051 | GXPReadyMode | itens da sala de espera | B | room.py (só memória) |
| 0x6052 | — | lista de itens (ids 0xAAA7A…) | grava os itens da sala de espera | M | room.py (só memória) |
| 0x6054 | 0x6055 | XPBugleChatDlg, "Bugle.xes" | "usar item": subtipo 2 = megafone (implementado), 6 = cards, 7 = ovo de pet | A | lobby.py |
| 0x6056 / 0x6058 | 0x6057 / 0x6059 | CPopup_JackpotBomb | **jackpot** e bomba do jackpot | A | jackpot.py |
| 0x6106 / 0x6108 | 0x6107 / 0x6109 | XPReadyEventDlg | evento na sala de espera | M | events.py (valor do config) |
| 0x6117 | 0x6118 | CPopup_JewelEnchant | encantamento de joia | A | enchant.py (recusa) |
| 0x7010 | 0x7011 / 0x7031 | ServerMode, data "(GMT+9)" | painel do canal: sai depois do 0x2001 ok, no lugar do 0x1090, porque a flag `+0x68780` vale 1 (construtor `0x41fa8d`; envio `0x515143`) | M | lobby.py (ranking + 0x7031) |
| 0x7012 | 0x7013 | login (`0x5148cf`) | lições do tutorial liberadas | A | events.py |
| 0x7014 | 0x7015 | fim do tutorial (`0x58517d`) | 0x7015 sem corpo fecha o tutorial (`0x413753`) | A | events.py |
| 0x7040 | 0x7041 | CPopup_Ranking (`0x5230e0` / leitor `0x4133d0`) | **janela Ranking** (abas, sub-abas, filtro de mobile, My Rank) | A | ranking.py |
| 0x7095 / 0x7098 | 0x7096 / 0x7099 | XPReadyEventDlg | missões / evento na sala de espera | M | — |
| 0x7110 | 0x7111 | XPSlotMachineDlg, "slot_start.xes" | **caça-níquel** | A | slot_machine.py |
| 0x7115 / 0x7410 | 0x7116 / 0x7411 | XPEnchantDlg (0x7410 para itens 0xC3502..0xC3569) | **encantamento** de item / carta de mobile | A | enchant.py |
| 0x7134 | 0x7135 | XPEnchantDlg | selos de avatar | M | enchant.py (recusa) |
| 0x7118 | 0x7119 | GXPShopMode | **desconto da loja** (ver "Loja: análise") | A | shop.py |
| 0x7124 | 0x7125 | XPRenaDlg | Rena (sorteio) | A | shop.py |
| 0x7128 | 0x7129 | XPShopMainDlg | desafio de encantamento | A | sem handler (de propósito) |
| 0x7130 | — | CPopup_Enchant_Challenge | fim do desafio de encantamento | A | events.py (só registra) |
| 0x7136 | 0x7137 | XPShopMainDlg | entrada na loja | A | shop.py |
| 0x7302 | 0x7303 | MyAvatar | usar booster no pet (ver "Pets") | A | — |
| 0x7308 | 0x7309 | CPopup_PetName | trocar o nome do pet | A | — |
| 0x7500 | 0x7501 / 0x7502 | XPChatComboBox | combos de chat | M | chat_combo.py |

## Opcodes novos que o cliente RECEBE (S→C) sem resposta direta acima
| Opcode | Onde | O que o cliente faz | Conf. |
|---|---|---|---|
| 0x101F | ServerMode | u32 ip + u16 porta: endereço UDP observado pelo servidor (NAT). O emulador manda (`managers/monitor.py`) | A |
| 0x1030 | global | u32 = id de texto do cliente (aviso), não texto livre | M |
| 0x1040 | global | bloqueia o chat por u32 segundos; o emulador manda pelo `/silence` | A |
| 0x1050 | ServerMode | presente chegou (sem corpo); o emulador manda pelo UDP admin 0xF020 | M |
| 0x1060 | global | aviso de e-mail não verificado (abre o ErrorCodeDialog do 0x1078) | M |
| 0x1111 | ServerMode | grava o **tipo do canal/servidor** (`DAT_0091f9d1`; 2 muda o filtro de salas para 0x10) | M |
| 0x1113 | global | lista `u16 n + u32[n]` (amigos / mudos) | M |
| 0x2025 | GameList `0x4d607b` | convite recebido (u16 sala, senha 4, msg 20, apelido 12) | A |
| 0x2131, 0x2132 | GameList | entrada rápida: falha / sala criada | A |
| 0x21F8 | GameList | campo novo da lista ao vivo, gravado e não usado | M |
| 0x3107, 0x3451 | Ready | respostas de 0x3106 / 0x3450 | A |
| 0x4414, 0x4502 | Play | campos de resultado que o cliente não lê / subiu de patente | B |
| 0x4415 | PlayMode `0x5018f0` | tela de resultado (gold/GP por jogador); o emulador manda depois do 0x4412 | A |
| 0x6005 | global | **aviso de presente**, um por GiftMsg (ver "Loja: análise") | A |
| 0x6116 | Play | encantamento/joia na partida | B |
| 0x7113 | global | fichas do caça-níquel (push) | A |
| 0x7117 | global | pontos de desconto (push); o emulador não manda (ver "Desconto") | A |
| 0x7121, 0x7122 | global | **evento Pumpkin** (XPPumpkinDlg) | A |
| 0x7123 | global | saldo da Rena (push; com a flag do Pumpkin vai para o XPPumpkinDlg) | A |
| 0x7127, 0x7202 | global | presença / encantamento [INCERTO] | B |
| 0x7300, 0x7301 | global | **pets** (lista e status) | A |
| 0x7303..0x7307, 0x7309 | Shop / global | respostas e pushes de pet | A |
| 0x7401, 0x7402 | global | **Mobile Card Booster** (CXPShopMobileCardBoosterDlg) | A |
| 0x7133 | ServerMode | carrega texto 0x122 | B |
| **0x9001** | ServerMode | 1º byte 0 → segue (`FUN_00433530`); senão, popup de erro 6 | M |

Os 0x6020, 0x6023 e 0x6026–0x6028 que uma leitura anterior listava como avisos **não** estão no handler global.

## Sistemas novos (classes de janela que o v440 não tem)
Amigos (XPBuddyDialog/XPBuddyChatDlg), megafone (XPBugleChatDlg), chat colorido, emoticons, encantamento (XPEnchantDlg, CPopup_JewelEnchant, CPopup_Enchant_Challenge),
pets (CPopup_PetBooster/PetInfo/PetName), boosters (CPopup_ItemBooster, CXPShopMobileCardBoosterDlg), jackpot, slot machine, missões, lista de mudos, troca de nick (NameChangeDlg),
ranking, evento Pumpkin, Rena, tutorial, convite e ir para sala.

## Como o servidor trata a versão
Um servidor só, com **fase por game server** (`gameservers[].phase`): TH → WCS1 → WCS2 em `gunbound/game/phase.py`,
cada uma herdando a anterior e declarando só a diferença (`add`/`replace`/`remove` de opcodes e métodos de layout).
É por servidor e não por jogador, porque a sala manda o mesmo pacote para todos. A fase é escolhida pelo nome e não pelo número de
versão porque famílias de cliente (GBS, GLS, GIS…) têm numerações próprias. O v548 e o v584 usam a WCS2; o v584
tem Tiburon/Frank/Maya/Phoenix/Wolf/Blue Whale, ausentes no v440.

## Layout dos pacotes comuns: v440 x v584
Comparação da leitura/montagem do corpo nos dois clientes: v440 (sha `9609f7e2…`) e o dump v584.
Usei o REA nas funções já definidas e o Ghidra 12.1.4 headless nas que só são alcançadas pela vtable.
Os offsets são em bytes, contados a partir do início do corpo (depois do cabeçalho de 6 bytes).

| Opcode | Direção | Resultado | Detalhe |
|---|---|---|---|
| 0x1010 login | C→S | **MUDOU** | v440: 20 + u32 + u32 + u16 + u32 (versão) = 34 bytes antes da cifra. v584: os mesmos campos **+ 16 bytes** no fim (`DAT_0091f9ec..f8`), que o leitor ignora (lê blocos fixos), e o ProductVersion depende da chave de região (abaixo). A WCS2 aceita os 4 valores |
| 0x1012 login (resposta) | S→C | igual | mesmos offsets 0x01..0x49 (o v584 também lê o byte em +0x12 como flag). Depois dele o v584 espera 0x1031 RTC 0 para pedir o canal (`login_ready`) |
| 0x101F | S→C | igual | u32 + u16 |
| 0x1102 lista de servidores (broker) | S→C | igual | mesma sequência de campos |
| 0x2001 entrada no canal | S→C | igual | — |
| 0x201F chat do canal (cifrado) | S→C | **MUDOU** | v440: tamanho em +13 e texto em +14. v584: tamanho em +15 e texto em +16 (2 bytes novos depois do apelido) |
| 0x21F1..0x21F7 lista ao vivo | S→C | igual | — |
| 0x2105 detalhe da sala | S→C | **MUDOU** | registro de jogador: 0x1E bytes no v440, **0x22** no v584 (+ u32 em +0x1E) |
| 0x2111 entrar na sala | S→C | cabeçalho igual | offsets +1/+5/+9/+0xD/+0xE/+0xF iguais. O servidor manda os itens com 10 bytes, como no 0x3010 (mesmo `write_player`) [INCERTO: leitor do 0x2111 não conferido] |
| 0x3010 jogador entrou na sala | S→C | **MUDOU** | cabeçalho igual até +0x2D (u16 = nº de itens). Cada item tem **4 bytes** no v440 (u32) e **10** no v584 (u32 + u16 + u32) |
| 0x3432 início da partida (cifrado) | S→C | **MUDOU** | cabeçalho (u32 + u8 + u16) e registro de jogador (22 bytes) iguais. Final: v440 = u16 evento + eco do 0x3430; v584 = u16 evento + **1 byte** + eco (seed u32 + blocos por modo: modo 3 6×3 bytes, modo 4 3×3) + **1 byte** final = bônus 0x4300 (0xFF = nenhum) |
| 0x4412 resultado (cifrado) | C→S | **MUDOU** | v584: u16 jogadores + registros de 23 bytes só com contagens de eventos; o servidor calcula gold/GP e responde 0x4415 (`wcs2/result.py`) |
| 0x5010 BCM | C→S | **MUDOU** | v584: u8 tipo, u8 cor, u8 tamanho, texto; tipo 8 = megafone (`wcs2/lobby.py`) |
| 0x1101 Grand Prix (lista) | S→C | **MUDOU** | grupo 44 bytes, pessoa 56, eu 44 (v440: 24/36/24) |
| 0x3020 / 0x3400 / 0x4102 | S→C | igual no início | mesmos primeiros campos (slot, u32). O corpo cifrado é lido em outras funções: [INVESTIGAR] |
| 0x6021 / 0x6009 / 0x6031 loja | S→C | [INVESTIGAR] | no v584 a leitura saiu da tela da loja (vai para diálogos/funções auxiliares); não comparei |
| 0x6001 baú | S→C | **MUDOU** | v584: `Recovered` + u16 nível de encantamento + u32 (o v548 lê só o `Recovered`) |
| 0x1032 cash | S→C | cifrado, u32 em +0 | o cliente grava o cash (`0x4102e6` → G+0x1b824); mandado depois do 0x1031 no login. Sem ele a loja abre com 0 até o 0x6101 |

Onde cada layout foi lido (feito na fase `WCS2`; campos sem significado conhecido vão em 0):

| Pacote | v440 | v584 | Onde |
|---|---|---|---|
| 0x2111/0x3010 itens | u32 por item | u32 + u16 + u32 | leitura nas telas |
| 0x2105 jogador | 0x1E: apelido 12, gênero, byte do slot, guild 8, 4 u16 | os 0x1E + u32 = 0x22 | original `0x42f2b0`; cliente v440 GameList, v584 `0x4d5760` |
| 0x201F chat (decifrado) | posição, apelido 12, tamanho (+13), texto (+14) | 2 bytes novos depois do apelido: tamanho (+15), texto (+16) | v440 `0x42a5f0`; v584 GameList |
| 0x3432 final | u16 evento + eco do 0x3430 | u16 evento, 1 byte, eco do 0x3430, **1 byte final** | 0x3430 v584 `0x433770` (seed u32 + modo 3: 6×3 + modo 4: 3×3, sem o byte final); leitor `0x508820` |
| 0x1101 GP | grupo 24, pessoa 36, eu 24 | grupo 44, pessoa 56, eu 44 | leitura `0x4d5760`; telas `0x538bf0` e `0x538750` |
| 0x1010 login | product_version 8452169 (0x0080F849) | uma de 4 constantes por chave de região (`0x409cb0`): Turkey 20090713, Arab 20090618, Brazil 0x04FCCB1C, nenhuma 0x03E524F5 | v440 `0x4f1e10`, v584 `0x5141c0` |

- 0x1101 v584: +0 aparece sozinho em "meu grupo"/"eu" (posição); +4 é negado pelo cliente; +0xC é texto de 20 bytes; +0x20/+0x24/+0x28 são as 3 colunas; o apelido da pessoa fica em +0x2C.
  [INFERIDO] Colunas = Pontos/Win/Lose e +8 = Category, por analogia com o v440 (os títulos das colunas são imagem). O texto do grupo é o número do grupo, porque o banco não tem nome.
- 0x1010: [NÃO DÁ PELO ESTÁTICO] O número de versão (comparado com `version_min/max`) vem de um valor protegido lido em tempo de execução (v440 `FUN_0042bfd0` → `FUN_004c66d0`). Ajuste `version_min/max` com o que o log `Recv Version(...)` mostrar. O `GunBoundEng.ini` é cifrado, então também não confirmei qual região está ativa.
- 0x2105 v440: o servidor mandava 25 bytes por jogador (sem o byte do slot e com u32 no lugar dos 4 u16), mas o cliente lê 30. Corrigido no `Phase` base (TH/WCS1). [INFERIDO] O byte do slot vai como o time do jogador.
- 0x3432: antes o byte final ia 0, que liga o bônus tipo 0; agora vai 0xFF (nenhum) ou o tipo sorteado por `bonus_event`.

## Pendentes no WCS2
Lista completa com o motivo de cada um em [README-WCS2.md](../README-WCS2.md).
- **0x7011:** ranking do XPRankingListDlg (dlg 0x25a, aba do 0x259): só o apelido (+0) e o grau (+0x1e) são desenhados
  (0x54f310), na ordem do pacote; os outros campos nunca são lidos. Status != 0 ignora o pacote sem limpar a lista.
- **0x7031:** quadro por país do XPReadyEventDlg (0x550170), sem pedido no cliente: u16 ignorado, 3 x u16 totais
  (ouro/prata/bronze), u16 n1, u16 n2, n1 x (u16 posição, u16 país, u32 pontos; a última linha mostra a posição),
  n2 x (u16, u16 país, 3 x u16 medalhas). Não aparece com PumpkinEvent=1 no INI. Detalhes em wcs2/lobby.py.
- **0x6054:** só o subtipo 2 (megafone). Subtipo 6 (cards) e 7 (ovo de pet) recusam (ver "Loja: análise").
- **Loja:** desafio 0x7128/0x7129/0x7131, pets 0x7300–0x7309, booster 0x7401/0x7402 (layouts abaixo).
- **Presente com o jogador online:** o 0x6005 só vai no login (resposta ao 0x6004); não há push na hora.
- **Eventos sem dados no emulador:** 0x7095/0x7098, Pumpkin 0x7121/0x7122, 0x7127, 0x7202, 0x6116, 0x7133.
- **Sem uso:** 0x4414, 0x4502, 0x7502 (u16 n + u32[n]), 0x21F8.
- **Globais S→C sem gatilho:** 0x1030, 0x1060, 0x1111, 0x1113, 0x9001.
- **Buddy:** o `Buddy2.dll` do v584 usa Id de 20 bytes e nick em UTF-16; suportado, layout em [BuddyServ.md](BuddyServ.md).

## Loja: análise (2026-10-19, Ghidra)

**Base da análise**
- Binário: `GunBound.gme` do cliente v584, sha256 `0bc124c6…f430` (o dump do início deste documento é `a0ba7802…`; os endereços batem).
- Ferramenta: Ghidra 12.1.4 headless.
- Os acessores de valor protegido (`0x41cd40` grava, `0x407f90` lê) foram marcados como `__thiscall`. Os offsets foram conferidos no asm.

**Convenções**
- "Corpo" é o que vem depois do cabeçalho de 6 bytes. Os campos são little-endian.
- G = `DAT_0091efd0` (dados do jogador).
- Lista do baú = G+0x266c0, registros de 0x3c bytes: +4 Chest.No, +8 Item, +0x14 flag "vestido", +0x1c Volume. O Volume foi confirmado pela leitura do 0x7401.
- Lista de avatares = G+0x266b0, registros de 0x30 bytes. Lista de pets = G+0x68ae0, registros de 0x78 bytes.

**Arquivos**
- Banco de referência: `db/gbwc.sql`.
- Não li os textos dos popups (ids 0x7a1xx/0x7c87x): ficam no GunBound.xfs do v584 (SolFS com senha).

### Correções na tabela do doc
- **0x7118/0x7119 não são pet.** São o **desconto da loja** (pontos em G+0x1b828).
- **0x7300/0x7301 não são o booster de card.** São a **lista de pets** e o **status do pet**.
  - O booster de card é só 0x7401/0x7402, itens 0xC3502..0xC3569.
- **0x6005 é aviso de presente (gift).** O v584 **não tem leitor da resposta 0x6004**: varri todas as tabelas de salto e nenhuma cobre 0x6004.
- **Pacotes S→C que o cliente nunca pede:** 0x7300, 0x7301, 0x7304, 0x7305, 0x7306, 0x7307, 0x7401, 0x7402, 0x7117, 0x7122, 0x7123.
  - **0x7304/0x7305 não são pedido e resposta.** Os dois são recebidos pelo cliente.
- **AvatarWearInfo.ini é cache local do cliente** (seção "All"). É lido no 0x7502 (`0x414ba1`) e gravado no MyAvatar (`0x5720b0`). Não tem relação com o 0x7302.
- **0x6054 é "usar item" genérico.** Corpo de 17 bytes: u8 subtipo, u16 0, u32 Chest.No, u32 0, u16 N, u32 Item.
  - **Subtipo 6:** pacote de cards 0xAAEAD..0xAAEB0. O cliente tira 10 do Volume e guarda o item em G+0x6f578.
  - **Subtipo 7:** ovo de pet 0xAAEC3..0xAAEC6. O cliente tira 30 do Volume. Antes, exige nº de pets + 1 ≤ (u8)G+0x681b0 + 5; senão mostra o popup 0x7a177.
  - [INCERTO] Qual pacote responde a cada subtipo. O provável: 0x7401 para o 6, e 0x7305 + 0x7306 para o 7.

### 0x6005 (S→C, handler global `0x41256b`)
**Layout:** sem RTC, um registro por pacote.

| Offset | Tipo | Campo |
|---|---|---|
| +0x00 | u32 | Item (= GiftMsg.MenuId; neste banco Menu.No = Item1). Escolhe a imagem pelas faixas de item. |
| +0x04 | u32 | GiftMsg.No. É a chave: o cliente descarta repetidos. |
| +0x08 | u8 | [INCERTO] tipo; hoje o servidor manda 1. |
| +0x09 | char[12] | apelido de quem enviou |
| +0x15 | u32 | time_t (exibido como aaaa.mm.dd) |
| +0x19 | u8 | len |
| +0x1a | char[len] | texto |

**O que o cliente faz:**
- Copia o registro para um registro de 0xa0 bytes (texto em +0x1d) e o põe numa fila em G+0x68ab4.
- Liga a flag G+0x1b308.
- O popup `FUN_0055ecd0` tira um registro da fila por vez; a resposta do jogador sai pelo 0x6008, que já existe.

**Risco:** o `len` não é conferido. Mais de 0x83 bytes estoura o registro. GiftMsg.Msg é varchar(255), então o servidor deve **limitar a 0x82**.

**Servidor (WCS2), feito em `wcs2/shop.py`:**
- No login ok, o cliente limpa a fila e manda 0x6004. A resposta 0x6004 de `item_gift_msg.py` é ignorada no v584.
- O 0x6004 é respondido com **um 0x6005 por linha de GiftMsg**, sem RTC, texto cortado em 0x82 bytes.
- Falta: mandar um 0x6005 na hora em que o jogador recebe um presente estando online (hoje só aparece no próximo login).

### Desconto da loja: 0x7117, 0x7118 → 0x7119

**0x7117 (S→C, global `0x4139b2`)**
- u16 rtc. Com rtc 0, um u32 vai para G+0x1b828; com outro rtc, G+0x1b828 = -1.
- O MyAvatar mostra o valor (texto 0x7a16e) quando não é -1.
- **Valor inicial:** 0 na construção e -1 no reset (`0x42264e`). Sem um valor, os botões de desconto nunca habilitam.
- O emulador não manda o 0x7117: o modo 1 sai a cada entrada na loja e a resposta 0x7119 já grava os pontos.

**0x7118 (C→S, envio `0x51a170`):** u8 modo.
- **Modo 1:** sai sozinho em toda entrada na loja (`0x518237`).
- **Modo 2:** botão 0xB7, exige G+0x1b828 ≥ 50. **Modo 3:** botão 0xB8, exige ≥ 100.
- O modo fica em ShopMode+0x8c.
- `FUN_00575860` multiplica os **10 preços** (Gold W/M/I/T/Y e Cash W/M/I/T/Y) por **1.0, 0.8 ou 0.5** em float e trunca (`__ftol`).

**0x7119 (S→C, ShopMode `0x516fa3`):** u16 rtc.
- **rtc 0:** u32 vai para G+0x1b828. Se o modo não é 1, o cliente recalcula os preços da lista e desabilita os botões.
- **rtc ≠ 0:** o cliente volta ao modo 1 e reabilita os botões.

**Servidor (feito em `wcs2/shop.py` e `item_buy.py`):**
- O 0x6020 (compra) **não leva o modo**: só u32 menu, u8, u8 e a cifra (`0x54083c`).
- Por isso o fator fica guardado na conexão (o modo 1 zera) e o `item_buy.py` aplica com truncamento. O presente
  (0x6030) paga cheio.
- Modo fora de {1, 2, 3} recusa. Custo no servidor: 0, 50 ou 100 pontos, debitados no 0x7118; a resposta leva o saldo novo.
- [INCERTO] se o original debitava no 0x7118 ou na compra.
- **Banco:** coluna `Game.DiscountPoints`.

### Rena: 0x7124 → 0x7125

**0x7124 (C→S):** vem do XPRenaDlg, comando 0x191 (`0x55f5d0`). Corpo: u32 = 100, constante.
- O botão só habilita com G+0x1b82c ≥ 100 (`0x55f514`).

**0x7125 (S→C, global `0x413e1f`):** u16 rtc.
- **Sucesso (rtc 0):** u32 ItemGanho em +2 e u32 SaldoRena em +6. O saldo vai para G+0x1b82c.
  - O XPRenaDlg procura o item na tabela de itens do cliente (`FUN_004306c0`, mesmos ex*.dat): achou, mostra o prêmio (estado 3); não achou, mostra falha (estado 2).
- **rtc ≠ 0:** a janela recebe -1 e mostra falha. O saldo não muda.
- Com a flag `0x91f9d5` = 1 (evento Pumpkin), a resposta vai para o XPPumpkinDlg; rtc 0x25 mostra o texto 0x451.
- O cliente **não debita nada localmente** e **não insere o item** na lista do baú.

**Valor inicial:** G+0x1b82c também começa em 0 ou -1. O servidor deve mandar **0x7123** depois do login (u16 0 + u32 saldo vão para G+0x1b82c; rtc ≠ 0 grava -1).
- O 0x7122 (u16 0 + u32) grava G+0x1b834, um 2º contador exibido junto (`0x550600`).

**Servidor (feito em `wcs2/shop.py`):**
- Ignora o u32 do pedido e cobra 100 de `Game.RenaPoints`.
- Sorteia o item da chave `rena` do config (sem a chave, recusa), insere em Chest e responde com o saldo novo.
- O 0x7123 (saldo) vai junto da resposta do 0x7012 no login.
- O 2º contador (+0x1b834, 0x7122) não tem coluna.
- [INCERTO] O item só aparece no baú quando o 0x6001 for reenviado.

### Desafio de encantamento: 0x7128 → 0x7129 (→ 0x7130 → 0x7131)

**0x7128 (C→S):** vem do XPShopMainDlg, comando 0xB9 (`0x577967`). Corpo: u32 Chest.No do ticket 0xAAECC, u32 Chest.No do alvo, u32 Item do alvo.
- O alvo é o item selecionado no XPShopListDlg; pode estar na lista de avatares ou na do baú.
- Sem ticket, o cliente mostra o popup 0x7c87d.

**0x7129 (S→C, ShopMode):** u16 rtc. Só tem efeito com rtc 0; outro rtc não faz nada.
- **Corpo de sucesso:** u8 R em +2, u32 Chest.No do ticket em +3.
- O cliente **tira 10 do Volume do ticket** e apaga a linha quando chega a 0.
- Abre o CPopup_Enchant_Challenge com +0x9c = R.
  - O minijogo tem até 9 rodadas. O jogador ganha a rodada enquanto R > rodada atual. Na rodada 8 aparece o texto 0x7c87c.
  - Ou seja, **R é o resultado que o servidor decide** (rodadas que o jogador vai ganhar).
- No fim, o cliente manda 0x7130 (vazio).

**0x7131:** u16 rtc; com rtc 0, u16 n em +2 e itens a partir de +4.
- O cliente remove o alvo (pelo Chest.No) e insere os itens novos (`FUN_004361f0`).
- Formato de cada item: u32 No, u32 Item, u8, u8 acq, u8 flag+[u32 segundos], u8 flag+[u32 vol], u8 flag+[u32].
- Se o item removido for 0x321ee, G+0x68b40 passa a 2.

**Servidor:**
- Validar que o jogador é dono do ticket e do alvo.
- Tirar 10 de Chest.Volume do ticket no mesmo momento do 0x7129.
- Guardar R para usar no 0x7130.
- [INCERTO] A regra de prêmio do 0x7131 não está no cliente. Enquanto não houver regra, o 0x7128 **fica sem resposta**: responder só o 0x7129 queima ticket sem prêmio.
- O Menu.Volume1 do 0xAAECC precisa ser múltiplo de 10.

### 0x7136 → 0x7137
- **0x7136:** vazio. Sai do comando 0xBB (`0x577a8d`) só quando ShopMode+0x90 = 0, ou seja, uma vez por entrada na loja.
- **0x7137:** u16 rtc.
  - **rtc 0:** ShopMode+0x90 = 1 e `FUN_0056ad40` redesenha a lista e reaplica os itens vestidos no preview do MyAvatar. Nenhum dado vem do servidor.
  - **rtc 0x28 / 0x29:** textos 0x2cd e 0x2ce.
- [INCERTO] O significado do botão. O emulador responde rtc 0, sem tocar no banco.

### Pets: 0x7300, 0x7301, 0x7302 → 0x7303, 0x7304, 0x7305, 0x7306, 0x7307, 0x7308 → 0x7309

**Registro de pet no cliente** (0x78 bytes; a chave é o **Chest.No** do item de pet 0x40001..0x48001):

| Offset | Campo |
|---|---|
| +0 | No |
| +4 | Item |
| +8 | S8 |
| +0xC | U0C |
| +0x10 | vestido |
| +0x14 | Energia |
| +0x18 | 5 slots × {u32 Chest.No, u32 Item, ptr} |
| +0x54 | Lovely (≥100/500/1000 mostra o efeito "Pet_Lovely_100/500/1000") |
| +0x58 | nome |

**Origem e semântica dos campos:**
- O 0x6001 já cria o registro (No, Item e vestido). Pet vestido com Energia < 1 faz o cliente mandar o **0x600E de desvestir** (u16 1, u32 No, u8 0).
- [INCERTO] S8: o booster 0x321e9 força S8 = 15 nos pets 0x40001/0x40007 e 75 nos outros.
- Os boosters de pet são os itens 0x321e9..0x321ed (`FUN_00435d30`). O 0x321ee aumenta os slots abertos.

**0x7300 (S→C, `0x413f5b`)**
- Cabeçalho: u16 SlotsAbertos (vai para G+0x68b40) e u16 n.
- Se n > (u8)G+0x681b0 + 5, o **pacote inteiro é ignorado**. [INCERTO] G+0x681b0 sobe 1 por um certo item do baú (máximo 5).
- Cada registro tem 0x4a bytes:

| Offset | Tipo | Campo |
|---|---|---|
| +0x00 | u32 | Chest.No |
| +0x04 | u32 | Item (0x40001..0x48001) |
| +0x08 | i16 | S8 |
| +0x0A | u32 | Energia |
| +0x0E | u32 | U0C |
| +0x12 | u32 | Lovely |
| +0x16 | 5 × {u32, u32} | slots: Chest.No e Item do booster |
| +0x3E | char[12] | nome |

- O registro casa com o existente pelo **Item**, não pelo No.
- **Item fora da faixa desalinha o resto:** o cliente pula o registro sem ler os slots nem o nome.
- Pet vestido com Energia > 0 é criado na tela. Com Energia ≤ 0, o cliente manda 0x600E.

**0x7301 (S→C, `FUN_00417f90`):** 18 bytes. Só tem efeito com um pet ativo.
- Corpo: u32 No, u32 ignorado, i16 S8, u32 Energia (vai para +0x14), u32 U0C.
- Se S8 subiu, liga uma flag de efeito.
- Energia < 1: o cliente manda 0x600E e remove o pet da tela.
- Na partida, repassa por P2P (0xC310).

**0x7302 (C→S, MyAvatar `0x5736ed`):** usar um booster 0x321e9..0x321ed no pet atual.
- Corpo: u32 PetNo, u32 PetItem, u32 Chest.No do booster, u32 Item do booster.
- Checagens no cliente:
  - booster já usado num slot aberto: popup 0x7a176;
  - slots abertos cheios: popup 0x7a173.

**0x7303 (S→C):** u16 rtc.
- **rtc 0:** u32 Chest.No do booster e u32 Item vão para o 1º slot vazio do **pet atual**; popup 0x7a172. Não mexe no baú.
- **rtc 0x1d:** popup 0x7a176. **rtc 0x25:** popup 0x7a173.

**0x7304 (S→C):** 46 bytes. Sobrescreve os 5 slots.
- Corpo: u32 PetNo, u16 S8, 5 × {u32 Chest.No, u32 Item}.

**0x7305 (S→C):** pet novo, 14 bytes. [INCERTO] provavelmente o resultado do ovo.
- Corpo: u32 No, u32 Item, i16 S8, u32 U0C.
- O cliente adiciona o pet com Energia 250, Lovely 0, não vestido e sem slots.
- Abre o CPopup_PetBooster com +0xb8 = S8.

**0x7306 (S→C):** u16 rtc. Com rtc ≠ 0, só imprime "NS_PET_BOOSTER_AVATAR_INFO Error".
- **rtc 0:** u16 n e n × {u16 prêmio, u32 No, u32 Item, u8, u8 acq, u8 flag+[u32 seg], u8 flag+[u32 vol], u8 flag+[u32]}.
- Prêmio 1..4: mostra 3000/5000/10000/100000. Prêmio 5: o item entra na lista de avatares.
- Depois o cliente manda **0x6100 e 0x6104**. O servidor precisa creditar o prêmio antes de responder esses dois.

**0x7307 (S→C):** 14 bytes. Grava S8 e U0C.
- Corpo: u32 PetNo, u32 ignorado, i16 S8, u32 U0C.

**0x7308 (C→S, CPopup_PetName `0x521050`):** 24 bytes.
- Corpo: u32 Chest.No do ticket, u32 Item do ticket, u32 PetNo (ator +0x58), char[12] nome.
  - **Ticket:** 0xAAEBD só com ator+0x4c = 0; 0xAAEBE só com ator+0x4c ≠ 0.
  - **Nome:** 12 bytes crus do editbox. Ler até o 1º NUL.

**0x7309 (S→C):** u16 rtc; sempre fecha o CPopup_PetName.
- **rtc 0:** u32 PetNo e char[12] nome. O cliente grava o nome e atualiza a ShopList.
- **rtc 0x26 / 0x27:** textos 0x7a17a e 0x7a17b.
- O cliente **não consome o ticket**; [INCERTO] o baú só se corrige com o próximo 0x6001.

**Servidor e banco (pets):**
- Tabela nova **PetInfo** (No = Chest.No, PK): S8, Energia, U0C, Lovely, Nome varchar(12), mais os 5 slots (BoosterNo e BoosterItem), ou numa tabela filha PetSlot.
- Em Game: **PetSlots** (G+0x68b40) e **PetExtra** (G+0x681b0).
- **Ordem de envio:** mandar o 0x7300 logo **depois do 0x6001**.
- **Energia:** nunca mandar Energia ≤ 0 para pet vestido. O 0x600E que o cliente devolve vira Wearing = 0 no handler atual.
- **Validação:** conferir dono do pet, do booster e do ticket; limitar n.

### Booster de cards (CXPShopMobileCardBoosterDlg)

**0x7402 (S→C, global):** i16 n e n × {u32 Chest.No, u32 Item, i16 Nível} (10 bytes cada).
- O cliente zera os mapas G+0x68b44 e G+0x68b54. Só guarda o card cujo Item está na lista do baú, então **mandar depois do 0x6001**.

**0x7401 (S→C):** u16 rtc; com rtc 0, u16 n.
- Exige n + cards atuais (G+0x68b4c) ≤ 10; senão mostra o popup 0x7a15c.
- Cada item: u32 No, u32 Item, u8 vestido, u8 acq, u8 flag+[u32 segundos de validade], u8 flag+[u32 Volume], i16 Nível.
- O cliente **acrescenta o card à lista do baú**, aos mapas e à janela ("Lv.%d"; a classe sai de (Item-0xC3502)&3).

**Servidor e banco:** os cards são linhas de Chest, e o Nível vai em **ChestEnchant.Level**.
- É o mesmo item do 0x7410 (encantamento das cartas, implementado com as regras do 0x7115).

### Gold e cash
- Nenhum desses handlers mexe no gold (G+0x1b820) nem no cash (G+0x1b824). Esses dois só mudam pelo 0x6105 e pelo 0x6101.
- Os débitos locais do cliente são só de Volume:
  - ticket 0xAAECC: −10;
  - pacote de cards (0x6054 subtipo 6): −10;
  - ovo de pet (0x6054 subtipo 7): −30.
- O servidor precisa consumir o mesmo valor. O Menu.Volume1 desses itens deve ser múltiplo de 10 ou 30: o cliente só apaga a linha quando o Volume chega a 0.

### Pendências e riscos
- **Não verificado:**
  - os textos dos popups;
  - o significado de S8, U0C, ator+0x4c e do botão 0xBB;
  - a regra de prêmio do 0x7131;
  - qual resposta cada subtipo do 0x6054 espera;
  - qual item incrementa G+0x681b0.
- **Riscos:**
  - texto do 0x6005 com mais de 0x82 bytes estoura o cliente (o servidor corta);
  - registro de pet com Item fora de 0x40001..0x48001 desalinha o 0x7300.
