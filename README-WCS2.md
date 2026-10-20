# GBWC EmuServer: GunBound World Champion Season 2 (WC S2)

O que é próprio do WC S2. O que vale para todas as versões está no [README principal](README.md); o que o S2 herda
do S1 (país, Grand Prix, presentes, entrada rápida) está no [README do S1](README-WCS1.md).

| Cliente | Fase no `config.yml` | ProductVersion no login |
|---|---|---|
| WC S2 v548 | `phase: "WCS2"` | aceita os mesmos valores do v584 e o `product_version` do config |
| WC S2 v584 (BR, 2010) | `phase: "WCS2"` | depende da chave de região: Brasil `0x04FCCB1C`, Turquia `20090713`, Árabe `20090618`, nenhuma `0x03E524F5` |

Layouts do v584: [docs/Cliente v584 - pacotes.md](docs/Cliente%20v584%20-%20pacotes.md).

## Configuração própria do S2 (no item de `gameservers`)

| Chave | O que faz |
|---|---|
| `jackpot` | prêmios do jackpot (0x6056) |
| `jackpot_bomb` | prêmio da bomba por carta (0x6058); padrão = carta seguinte |
| `tutorial` | prêmio da 1ª conclusão de cada lição (gold, itens, avatar) |
| `grandprix.enabled` | liga o Grand Prix |
| `bonus_event` | % de chance por partida do bônus "+Gold/+GP" (0x4300); 0 = desligado |
| `result_rewards` | gold e GP por evento no fim da partida (o v584 só manda contagens) |
| `slot_machine` | tabela do caça-níquel: `[resultado, valor, peso]` (resultado 2/3 = item, valor = código) |
| `rena` | sorteio da Rena: `[item, quantidade, peso]`; sem a chave, megafone e joias |
| `game_points` | pontos por partida, padrão `{RenaPoints: 10, DiscountPoints: 5}` (sem fonte no jogo) |
| `mvp` | `false` desliga o MVP do 0x4415 (padrão: quem fez mais gold base) |
| `stage_channel` | `true` faz do servidor um canal Stage (missões do v584) |
| `country_board` | `false` não manda o quadro por país (0x7031) na lista de canais |
| `jewel_enchant` | receitas do 0x6117: `[id, produto, ?, ?, Emerald, Ruby, Diamond, req1 tipo, req1 valor, req2 tipo, req2 valor]` por linha, na ordem do `JewelEnchantList.dat` do cliente |
| `event_6107_id`, `event_7013_value` | respostas fixas de eventos (o 0x6109 manda o `TotalScore`, como o original) |

### Colunas do banco usadas pelo S2

| Coluna | Uso |
|---|---|
| `Game.EventScore2` | fichas do caça-níquel |
| `Game.EventScore3` | progresso do tutorial |
| `Game.DiscountPoints` | pontos de desconto da loja (50 = 20%, 100 = 50%) |
| `Game.RenaPoints` | saldo da Rena (100 por sorteio) |
| `ChestEnchant.Level` | nível de encantamento |
| `ChestEnchant.Seal` | selo do avatar (u32 do 0x6001 e do bloco de avatar da sala) |
| `Game.ReadyItems` | itens de batalha da sala de espera (0x6050/0x6052) |

`DiscountPoints`, `RenaPoints`, `ReadyItems` e `Seal` são novas: em banco antigo, rode `python init_db.py WCS2`
(acrescenta as colunas). O cliente não mostra de onde vêm os pontos; aqui cada partida rende `game_points`.

## Diferenças de protocolo em relação ao S1

| Ponto | S2 (v584) |
|---|---|
| Login | o cliente só pede o canal (0x2000) depois do 0x1031 com RTC 0 |
| 0x2105 jogador no detalhe da sala | 0x22 bytes (u32 a mais, em 0) |
| 0x2111 / 0x3010 itens do jogador | 10 bytes por item |
| 0x6001 baú | `Recovered` + u16 nível de encantamento + u32 (o v548 lê só o `Recovered`) |
| 0x201F chat | cor do texto (+0xD) e 1 byte não lido depois do apelido |
| 0x2132 sala criada pela entrada rápida | 1 byte a mais |
| 0x3432 início da partida | evento de bônus no último byte |
| 0x4412 resultado | só contagens de eventos; o servidor calcula gold/GP e responde 0x4415 |
| 0x5010 BCM | tipo e cor antes do tamanho (megafone) |
| 0x6004 presentes | o cliente ignora a resposta 0x6004: quer um 0x6005 por presente |
| 0x1101 Grand Prix | grupo de 44 bytes, pessoa de 56 |

O v584 não desenha marca de amigo na lista de servidores (o código conta, mas não usa); as animações das linhas
vêm do campo de evento do 0x1102.

### Buddy

O `Buddy2.dll` do v584 usa Id de 20 bytes, nick/guild em UTF-16 e login **sem senha**: o servidor só aceita quem
está logado num game server a partir do mesmo IP. Não tem busca nem aviso (0x1FFE). Chat e pedido de amizade não
passam entre um cliente v584 e um TH/S1. Detalhes em [docs/BuddyServ.md](docs/BuddyServ.md#wc-s2-v584-buddy2dll-versão-0x1b).

## Opcodes só do S2

Legenda no [README principal](README.md#status-por-opcode).

### Canal, sala e partida

| Opcode | Status | Notas |
|---|---|---|
| 0x7010 → 0x7011 painel do canal | 🟡 | ranking por GP (a tela só mostra grau e apelido) + quadro por país 0x7031 logo depois (pontos = GP do país, medalhas = top 10/50/100; regras nossas, `country_board: false` desliga) |
| 0x6054 / 0x5010 / 0x5011 megafone | ✅ | gasta 1 item 0xAAE6E do baú e repassa o texto a todos; outros subtipos do 0x6054 recusam |
| 0x3450 / 0x3451 / 0x3452 / 0x2025 convite | ✅ | lista quem está no lobby do canal da sala; o aceite é um 0x2110 normal |
| 0x3106 alterar tudo | ✅ | |
| 0x6050 / 0x6052 itens de batalha da sala | ✅ | grava em `Game.ReadyItems` |
| 0x21F8 | — | campo da lista ao vivo que o cliente grava e não usa |
| 0x3433 fim do carregamento | ✅ | o cliente não espera resposta |
| 0x4412 → 0x4415 resultado | 🟡 | valores de `result_rewards`, MVP (mais gold) e `game_points` são nossos; aplica os fatores do servidor |
| 0x4300 bônus "+Gold/+GP" | ✅ | sorteado por partida com `bonus_event`; pago uma vez, tabela do cliente |
| Canal Stage (0x1111, 0x2120, 0x2103, 0x4520, 0x4412) | 🟡 | `stage_channel: true` no servidor: 0x1111 tipo 2 no login (os outros mandam 0), salas de 1/2 jogadores com a missão do 0x2120 repetida no 0x2103, sem mínimo nem equilíbrio de times; o 0x4520 do dono vira o 0x4410 (meta = vitória, tempo = derrota), morrer todos = derrota; 0x4412 de 30 bytes. As missões ficam no cliente (Lua); sem recorde/ranking de Stage (pacote não achado). `event: 4` dá o ícone de Stage na lista |
| S→C 0x4414, 0x4502, 0x7502 | — | 0x4414 vai para campos que o cliente não lê; 0x4502 (subiu de patente) não se aplica porque a patente vem do ranking; 0x7502 vazio não bloqueia nada |
| Patentes | 🟡 | escada de 47 ícones do v584 (pintinho 1 ... coroa de ouro 41, admin 0), o job diário grava essa numeração no banco (GP; medalhas e coroas também pela posição). Vale para v548 e v584. Banco vindo do S1: `python init_db.py WCS2`; `grade_min`/`grade_max` do config.yml também na numeração do S2 (1..41) ([Níveis](docs/Níveis.md)) |

### Loja e presentes

| Opcode | Status | Notas |
|---|---|---|
| 0x6004 → 0x6005 presentes recebidos | ✅ | um 0x6005 por presente; texto cortado em 0x82 bytes (mais que isso estoura o cliente). Presente recebido com o jogador online só aparece no próximo login (sem push) |
| 0x7118 → 0x7119 desconto da loja | ✅ | modo 1 (sem desconto), 2 (−20%, 50 pontos), 3 (−50%, 100 pontos); o desconto vale na compra (0x6020) seguinte; o presente (0x6030) paga cheio |
| 0x7124 → 0x7125 Rena | 🟡 | custa 100 `RenaPoints`, prêmio sorteado de `rena`; saldo (0x7123) vai junto da resposta do 0x7012 no login; pontos por partida (`game_points`) inventados |
| 0x7136 → 0x7137 | ✅ | o cliente só redesenha a lista |
| 0x7128 desafio de encantamento | — | sem resposta de propósito: o prêmio (0x7131) não está no cliente e responder só o 0x7129 queimaria o ticket |
| Pets 0x7300–0x7309 | — | o servidor precisa de tabela de pets (energia, slots, nome) que o banco não tem; layouts em `docs/Cliente v584 - pacotes.md` |
| Booster de cards 0x7401 / 0x7402 | — | push sem pedido do cliente; depende do 0x6054 subtipo 6, não implementado |

### Recursos

| Opcode | Status | Notas |
|---|---|---|
| 0x7012 / 0x7014 tutorial | ✅ | progresso em `Game.EventScore3`; prêmio na 1ª conclusão via `tutorial` |
| 0x6056 jackpot | 🟡 | prêmios por `jackpot`; alguns campos da resposta desconhecidos |
| 0x6058 bomba do jackpot | ✅ | gasta 12 (Rare) / 15 (Epic) cartas e dá a carta seguinte |
| 0x7115 encantamento | 🟡 | taxas de sucesso definidas por nós, não do original |
| 0x7410 encantamento das cartas de mobile | ✅ | mesmas regras do 0x7115 |
| 0x6117 jóias | 🟡 | receitas em `jewel_enchant` (colunas do `JewelEnchantList.dat`); o .dat real está no xfs, então as receitas padrão são nossas (Emerald/Ruby/Diamond -> joias do encantamento) |
| 0x7134 selos | ✅ | regras do cliente (até 4 atributos, sem repetir, Reset Seal zera); bônus 3/6/9 pelo nome do item; valor em `ChestEnchant.Seal` |
| 0x7040 ranking | 🟡 | abas e filtro por mobile aproximados; percentis aproximados; lê a tabela inteira |
| 0x7110 caça-níquel | ✅ | fichas (`Game.EventScore2`) ou cash; prêmios (fichas, gold, item) em `slot_machine`; 0x7113 com as fichas no login |
| 0x7500 combos de chat | ✅ | |
| 0x6108 → 0x6109 | ✅ | `TotalScore` do banco (servidor 2007, `SVC_GP` -> `GDBIN_GP`: o opcode já existia no S1) |
| 0x6106 → 0x6107 | 🟡 | só responde se `event_6107_id` estiver no config |
| 0x1078 → 0x1079, 0x7130 | ✅ | confirmação do aviso de e-mail; fim do desafio de encantamento (só registra) |
| 0x7095/0x7098 missões, abóbora 0x7121–0x7123, 0x7127 presença, 0x7202, 0x6116, 0x7133 | — | o servidor teria que empurrar dados de eventos que o emulador não tem |

## Comandos

### GM (chat)

Os comandos de GM do [README principal](README.md#comandos-de-gm-no-chat-autoridade--99-userauthority) valem no S2.
Para calar alguém use `/silence nick segundos`: no S2, `/mute` é tratado pelo próprio cliente (lista de ignorados).

### Tratados pelo próprio cliente S2

| Comando | O que faz |
|---|---|
| `/h`, `/help`, `/guide`, `/?` | lista de comandos (local) |
| `/kick apelido` | mestre expulsa (0x3150) |
| `/go N` | página N da lista de salas (0x2100) |
| `/goto N` | marca a sala N (local) |
| `/gg` | inicia a partida (0x3430) |
| `/mute`, `/mutelist`, `/loudall` | lista de ignorados (local) |
| `/key`, `/ipconfig`, `/quit`, `/exit` | locais |
| `/logging` | P2P entre os jogadores da sala |
| `/<emote>` | emotes P2P |
| `/lag` | não faz nada |
| `/<evento>` (`ChooseEvent.txt`) | mestre liga um evento na sala (0x3101): o servidor grava o settings cru e repassa, como o original; quem interpreta o evento é o cliente |

O S2 não tem `/to` (cochicho): use o Buddy.
