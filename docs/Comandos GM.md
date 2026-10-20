# Comandos de GM (detalhes de protocolo)

A lista de comandos para o usuário está no [README](../README.md#comandos-de-gm-no-chat-autoridade--99-userauthority).
Aqui fica o que o servidor faz por baixo. Extraído do servidor original (`GunBoundServ3.exe`, `FUN_00425a10`, via REA).
Implementação: `gunbound/game/protocol/gm_commands.py`.

## Transporte

- O cliente envia o texto cru do comando (ex.: `/bcm -a oi`) em **0x5100**. A resposta volta em **0x5101**, também
  com texto cru.
- Só aceita `User.Authority >= 99` (o admin de teste tem 100). Para quem não é GM, o comando é ignorado em silêncio,
  como no original.
- Comandos que o cliente já tratou e depois manda crus (`/gg`, `/goto`, cores, comandos ocultos do S2) não recebem
  "Syntax Error" (`CLIENT_ONLY`).
- **0x5010** (SVC_BCM, cifrado) repassa a mensagem de GM a todos em 0x5101. No S2 o 0x5010 tem tipo e cor antes do
  tamanho e também é o megafone (`wcs2/lobby.py`, ver [README-WCS2.md](../README-WCS2.md)).

## O que cada comando mexe

| Comando | Efeito no servidor |
|---|---|
| `/ban -e\|-dN\|-hN id [motivo]` | grava `User.RestrictTime` (`-e` = até 2099) e derruba a sessão; o login recusa enquanto valer |
| `/close N` | manda **0x3FFF** a cada jogador da sala N e tira todos |
| `/motd -c` / `-r` | troca o `announcement` do servidor ou o MOTD das salas, só em memória |
| `/qsman N` | tamanho da sala `QuickStartRoom` que a entrada rápida cria quando não acha sala livre (2/4/6/8; outro valor = 8) |
| `/qsopt 1..4` | modo da entrada rápida (Solo, Tag, Score, Jewel), usado para achar e para criar a sala |
| `/silence nick segundos` | **extra**: manda **0x1040** (u32 segundos; 0 tira). O bloqueio e o contador ficam no cliente; não grava no banco. No S1 `/mute` faz o mesmo |
| `/startgame` | **extra**: o GM mestre inicia a partida sem a checagem de prontos e times (dá para jogar sozinho). O botão Iniciar também funciona para o GM sozinho (`Room.start_check`) |

## Multiplicador (GoldFactor/ScoreFactor)

`gold_factor` e `score_factor` (% em `config.yml`) vão ao cliente no login.

- **TH e S1:** o cliente já aplica os fatores no resultado (0x4412). O servidor **não multiplica de novo**; só escala
  o teto anti-trapaça: gold `3000 × gold_factor/100` e GP `200 × score_factor/100` (`reward_caps` em `game_play.py`).
- **S2 (v584):** o 0x4412 só traz contagens. O servidor calcula gold/GP (`result_rewards`), **aplica os fatores** e
  mostra no 0x4415 (`wcs2/result.py`); o mesmo teto vale.
