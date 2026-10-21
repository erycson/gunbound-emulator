# Bots de sala

Status: **em construção**. Pronto: o bot entra e sai da sala (`gunbound/bot/room.py`), curva de acerto, penalidades
e perfis de mobile, o log do túnel, o carregamento e o ciclo de turno (`gunbound/bot/match.py`, estágio 1a: o bot
passa a vez e a partida não trava), a morte (1b) e o tiro (2, só S2 e mapas 0..10; fora disso o bot passa a vez).
Falta validar jogando: física ajustada pela captura, mobiles com tiro especial e as fases TH/S1.

### Na sala (`gunbound/bot/room.py`)
- `BotConn` imita o `ClientConnection` sem socket; tudo que a sala manda para ele é descartado.
- Entra como um jogador comum (0x3010 para a sala), sempre pronto, com patente, guild vazia, roupa sorteada pela
  patente (cabeça, corpo e bandeira da `Menu`, cash vale 100 gold na conta) e mobile sorteado entre os da versão.
- O mestre nunca vira bot; sala só com bots fecha. O kick do mestre e o `/close` também tiram bots.
- Prêmio (`bots.reward`, padrão 0): bot não recebe; com bot na sala, os outros recebem o fator.
- Só o mestre de uma sala comum aguardando usa `/bot` (não em Grand Prix, QuickStart nem Stage).
- **[INCERTO]** se o cliente manda o 0x5100 de quem não é GM. Se não mandar, só GM consegue usar `/bot`.

## Desenho combinado

- **Acoplável:** só existe no game server com `bots.enabled`; os comandos se registram quando ligado.
- **Comandos (para todos):** `/bot add [lvl] [mobile]`, `/bot remove [nome|all]`. Sem `lvl`, o nível é a média da
  sala, e o bot entra no time mais fraco. O kick do mestre também tira o bot.
- **`auto`:** no lugar do `lvl` ou do mobile, o mesmo que omitir (`/bot add auto auto`). O apelido termina em `[BOT]`
  (até 7 letras + sufixo, 12 bytes no fio); o `/bot remove` aceita o nome com ou sem o sufixo.
- **Escolher o mobile:** opção acoplável à parte, só para GM.
- **Nível por versão:** a patente vira `n` de 0 (pintinho) a 1 (topo): TH/S1 19..-4, S2 1..41 (`skill.normalize`).
- **Equipamento:** sorteado pela patente e pelo preço do item na `Menu`; nome aleatório. O bot pertence à sala,
  não existe no banco.
- **Prêmio:** opção por servidor para zerar ou reduzir gold e GP de partidas com bot.
- **IA (depois, desligada por padrão):** cliente compatível com a API da OpenAI (`base_url`, `model`, chave por
  variável de ambiente), para conversa e para estratégia (alvo, tiro, item, mover). Nunca decide a mira.

## Acerto (`gunbound/bot/skill.py`)

`base(n) = 0,95 - (0,95 - 0,25) * e^(-3n)` e `acerto = base(n) * PROD(1 - pen * (1 - 0,5n))`: o topo sente metade
de cada dificuldade. Penalidades cheias: distância 35% (linear), vento 30% (pela força), clima no caminho 25%,
parede 20%, morro 15%, SS 10%, ângulo até `max_pen` do tiro (^1,5 fora das faixas boas, 0 para baixo) e alvo perto
demais para tiro que precisa de espaço até 30%. Tudo em `bots.skill` do game server.

| n | base | 45°, meia distância, vento médio | 150°, longe, vento forte, clima, parede |
|---|---|---|---|
| 0 | 25% | 18% | 6% |
| 0,5 | 79% | 61% | 28% |
| 1 | 92% | 77% | 47% |

## Mobiles (`gunbound/bot/profiles.py`)

Por fase e por tiro (1, 2, SS): faixas de ângulo boas, distância mínima, peso do vento e da distância, e se o tiro
tem trajetória própria (`special`, a mira precisa simular). Os valores são **estimativas para ajustar jogando**, não
leitura do cliente. O 0x0D e o 0x0E mudam do TH (Dragon, Knight) para o WC (Aduka, Kalsiddon). Os do S2 (0x13..0x18)
estão todos como trajetória própria até serem estudados.

## Partida: o que falta mapear

Turno, tiro, dano, item e chat de sala trafegam entre os clientes. No emulador tudo cai no túnel 0x4500/0x4501
(com `local_udp_fix` desligado, ver Protocolo-Salas.md 6.6), então o servidor vê os bytes, mas não conhece o formato.
Sabido (fontes de referência, estático): o servidor só decide a ordem inicial e o spawn (0x3432); o mestre gera a
semente do random da partida (vento, clima) no 0x3430 [INCERTO]; cada cliente calcula o próximo turno; o **dano é do
cliente de quem atira** e os outros repetem o registro de impacto. Para o bot, o servidor fala como atirador.

### Formato (análise estática do v584/v440, confirmado decifrando a captura)

O túnel carrega o mesmo frame do UDP: `u16 hdr` (`len & 0x3fff`, `0x8000` dado, `0x4000` confiável), `u8 seq`,
`u8 soma do cifrado`, e o payload em AES-128-ECB (zeros até múltiplo de 16). Chave =
`u16 server_id` (índice do servidor na lista do broker) + `"comsik"` + `u16 room_id` + `d2 22 ea fa ee 3a`.
O payload começa com `u16 tipo`. `tools/tunnel_decode.py` decifra o `tunnel_log`.

Tipos principais (v584): 0xc400 tiro (posição, ângulo/força como vetores, vento), 0xc409 SS, 0xc401 item, 0x8402
posição, 0x4001/0x4005/0x4006 virar/trocar tiro/mira (só UDP, não passam pelo túnel), 0xc412 passa o turno,
0xc302 relatório de fim de turno (todos mandam, o mestre espera todos), 0xc303 novo turno (só o mestre, com o
vento), 0x4002/0x4003 chat, 0x8201 progresso do carregamento, 0x82FF carregou, 0xc304 morte (mesmo corpo do TCP
0x4100). O passe da captura é 0xc301 (o 0xc412 não apareceu). O bot precisa mandar 0xc302 a cada fim de turno
(senão o mestre trava) e o 0xc301 no turno dele.

**Feito:** o carregamento. Depois do 0x3432 cada bot manda pelo 0x4501, a cada humano, 0x8201 (u8 slot, u8 etapa
1..3) e 0x82FF, com seq próprio por destino (`bots.load`).

**Feito (1a): o turno** (`gunbound/bot/match.py`). O `GameTunnelRecv` não repassa ao bot o que chega para o slot dele:
decifra e entrega a `match.on_frame`. O que o bot manda vai aos humanos e, como se viesse pelo túnel, aos outros bots.
- O mestre (0x42e798) conta um 0xc302 por (fase, slot) em G+0x66c64 e só fecha a fase quando todo slot do bitmask
  0x92c320 reportou (0x425650); ao fechar, decrementa (0x432850). Não lê o contador. Corpo: u8 fase, u32 contador,
  u32, u32 (no 0e, u32 delay em +5, só usado o do atirador).
- Regras (iguais ao slot 1 da captura, `tests/fixtures/bot_turn_replay.txt`): 0x8600 do mestre → 0f; qualquer
  0xc400/0xc409 → 0e 3 s depois; qualquer 0xc301 (inclusive o do bot) → 0f; 0xc300 do mestre (u8 vez, u16 turno,
  estado) → contador = turno+1 e 02; 0xc303 02 com a vez do bot → 3 s depois, 0xc301; qualquer 0xc304 → 0xc309
  (u8 vítima + corpo do 0xc304). Cada 0xc302 vai depois de um 0xc40a (x, y do spawn), como o cliente; o 0xc40a e o
  0xc309 caem no default do despachante (0x4dd8a0).
- 0xc301 = 01 + u16 delay + estado. O receptor (0x4df139) soma o delay no acumulador do slot (G+0x2956c, exceto
  0xffff/0xea60) e copia 0x60 bytes do estado do próximo turno, que o mestre ecoa no 0xc300. O bot manda delay 9000
  (passes da captura: 7200..9100) e o estado do último 0xc300 (o vento não muda no passe do bot).
- Diferença conhecida: o humano segura o 02 até os tanques assentarem (morte do mestre no fim do turno); o bot manda
  no 0xc300. O mestre só conta, então a ordem não importa.
- O bot não manda 0x8402 (posição) nem anda; o x/y dele vai no 0xc40a e no 0xc400 (y do chão, ver 2).
- [INCERTO] a captura é 1x1; com mais jogadores o mestre pode esperar o 0xc309 ou o 02 de outro jeito.

**Feito (1b): a morte.** Cada cliente calcula o HP de todos os tanques (tank+0x150, máximo em +0x14c, x em +0x8c,
y em +0x90); o servidor não calcula dano. O cliente se declara morto no fim do turno (0x482720: HP <= 0 ou
y >= 9000 → 0xc304 + 0x4100). Para quem não se declarou, o mestre, ao escolher o próximo turno (0x4f5aa0, menor delay
entre os vivos), manda 0xc312 (u8 slot); quem recebe responde 0xc314 (vazio, 0x4e0425); o mestre confere o HP/y do
tanque de quem respondeu e manda 0xc315 (u8 slot, 0x4e04bb); o dono manda 0xc304 (u32 causa, u8 matador) e o 0x4100
(0x4e0596). O bot faz esse caminho: 0xc312 com o slot dele → 0xc314; 0xc315 → 0xc304 + 0xc309 e a morte no servidor
(`announce_death`, o mesmo do 0x4100). Causa como o cliente (0x47b156): 1 inimigo, 2 aliado, 3 o próprio; o matador
é quem atirou por último (o cliente usa quem acertou por último).
- [INCERTO] o mestre só examina, a cada escolha de turno, os slots com delay menor que o melhor vivo até ali; o bot
  morto pode levar um turno a mais para ser confirmado.

**Feito (2): o tiro** (`gunbound/bot/aim.py`, `match.shoot`). Quem recebe o 0xc400 (0x4e075b) põe o atirador no x/y do
pacote, grava o vento global (G+0x283dc força, G+0x283e0 ângulo) e cria o projétil (fábrica 0x443310): a lista de
impactos do fim do pacote só move a câmera (0x458c30). Então cada humano simula o tiro e o dano; o bot só escolhe
ângulo e força.
- Projétil (0x445426..0x445671): pos = (x, y) << 8; v = força * 512 * (cos, -sin) / 100 (seno da tabela 0x5fd6b0,
  5 casas); a = (vento_x, gravidade - vento_y) << 8 / 100; gravidade do mobile (characterdata coluna 40, por slot em
  G+0x296bc + slot*0x104: 98, Mage/Lightning/Dragon 90, Aduka 94, J.Frog 92). [INCERTO] o alcance só bate com a
  captura com velocidade x5 (36 tiros, erro mediano ~25 px); o passo por frame que dá esse fator não foi achado.
- 0xc400 (layout da captura, que diverge 2 bytes da leitura à mão do receptor; vale o da captura): u16 x, u16 y, 01, 00,
  s16 ângulo absoluto (0 direita, 90 cima, 180 esquerda), u16 força, 01, 3x (s16, s16) boca do cano em relação ao pé
  (y para cima), s16 força e s16 ângulo do vento, 00, u8 n + n x (u8 tipo, u16 x, u16 y) dos impactos.
- Sequência do humano e do bot: 0x8006 (u16 x, u16 y, 00 01), ~1 s depois o 0xc400, e quando o tiro termina o 0xc40a
  + 0xc302 0e com o delay do turno em +5 (captura 7900..8900; o bot manda 8900).
- O vento é o do 0xc300 do turno (u8 força, u16 ângulo no começo do estado). O terreno é o .lnd (u32 w, u32 h, w*h
  bytes, 0 = ar) do graphics.xfs do S1 (`bots.graphics_xfs`, padrão `../clientes/WC-S1-v495/graphics.xfs`; o
  GunBound.xfs do S2 é cifrado): mapa = stage.dat[mapa], lado B = mapa + 11 (cave não tem B). O y do bot é o primeiro
  chão abaixo do spawn; os impactos de cada 0xc400 cavam crateras de raio fixo 30 na cópia do bot.
- Mira: inimigo vivo mais perto (último x/y que ele mandou), elevações 25..85 de 5 em 5, força 40..400; fica o tiro
  que cai mais perto (chão ou corpo de tanque). Erra pela chance de `skill.py`: força 10..25% para mais ou menos.
- [INCERTO] tiros especiais (Nak cavando, Boomer curvando, Turtle dividindo...) seguem a trajetória normal na mira.
  Mapas S2 acima de 10 (o v584 tem 18 por lado) não estão no xfs do S1: o bot passa a vez.

### Captura

Com `tunnel_log: tunnel-capture.jsonl` no game server, cada 0x4500 vira uma linha JSON (`from`, `to`, `playing`,
`hex`). Roteiro: dois clientes numa sala; trocar tanque, time e pronto; iniciar; um turno de cada: andar, mirar sem
atirar, carregar e atirar o 1, o 2 e o SS, usar um item, passar a vez, digitar no chat; terminar a partida. Anotar
a hora de cada ação ajuda a casar com as linhas. Desligar depois (o arquivo cresce rápido).
