# Bots de sala

Status: **em construção**. Pronto: o bot entra e sai da sala (`gunbound/bot/room.py`), curva de acerto, penalidades
e perfis de mobile, e o log do túnel. Falta: o bot **jogar** (turno, tiro, dano), que depende do protocolo P2P da
partida. Hoje uma partida com bot começa, mas o bot não age: os clientes devem ficar esperando por ele.

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
0x4100). O bot precisa mandar 0xc302 a cada fim de turno (senão o mestre trava) e o próprio 0xc412 no turno dele.

### Captura

Com `tunnel_log: tunnel-capture.jsonl` no game server, cada 0x4500 vira uma linha JSON (`from`, `to`, `playing`,
`hex`). Roteiro: dois clientes numa sala; trocar tanque, time e pronto; iniciar; um turno de cada: andar, mirar sem
atirar, carregar e atirar o 1, o 2 e o SS, usar um item, passar a vez, digitar no chat; terminar a partida. Anotar
a hora de cada ação ajuda a casar com as linhas. Desligar depois (o arquivo cresce rápido).
