# Grand Prix

Extraído do servidor original (`GunBoundServ3.exe`, via REA) e do cliente (`GunBound.gme`). No original o Grand Prix
roda dentro do próprio game server: fila, sala e ranking no banco (`GrandPrix_Personal` / `GrandPrix_Group`).

## Como funciona
- **Grupo**: cada jogador pertence a um grupo (`GrandPrix_Personal.Category`, número). Sem grupo, não entra na fila.
- **Fila (0x2140)**: o jogador entra; quando há `battle_player_count` jogadores de um grupo e outros tantos de um
  grupo **diferente**, o servidor cria a sala `GrandPrixRoom` (tamanho 2× `battle_player_count`). Quem fechou a
  partida é o mestre (time A, com seu grupo); o outro grupo fica no time B. Cada jogador recebe `0x21F5` + `0x2111`,
  igual a entrar numa sala. O original não responde ao 0x2140. **0x2141** tira da fila.
- **Ranking (0x1100 → 0x1101)**: grupos, top pessoal, meu grupo e eu (layout abaixo). Recalculado a cada
  `rank_interval` segundos e guardado em memória.
- **Pontuação** (no resultado da partida, 0x4412): pessoal `personal_win_score` / `personal_lose_score`.
  Grupo pela diferença `pontos do vencedor − pontos do perdedor` (original 0x418994):
  - diferença ≥ `big_rank_difference` (favorito venceu): `group_win_score_big_higher` / `group_lose_score_big_lower`
  - diferença ≤ −`big_rank_difference` (zebra): `group_win_score_big_lower` / `group_lose_score_big_higher`
  - senão: `group_win_score_small` / `group_lose_score_small`

## Configurar
0. **Marcar o servidor como Grand Prix na lista**: o cliente só pede o ranking (0x1100) e mostra o Grand Prix quando
   o servidor tem tipo 2 na lista do broker (byte após o índice, `event`; cliente 0x4f29b6 grava e 0x4ce522 testa
   `== 2`). O broker usa 2 sozinho para todo servidor com `grandprix.enabled: true`; nos outros vale o `event` (0 ou 1).
1. Bloco `grandprix:` no game server (em `config.yml`, servidor índice 1 já vem pronto, porta 8361). Só nas fases
   WCS1 e WCS2: com `phase: TH` o servidor não sobe.
   ```yaml
   grandprix:
     enabled: true
     battle_player_count: 1     # por grupo
     mode: SOLO                 # SOLO, SCORE, TAG, JEWEL
     stage: 0                   # mapa (0 = aleatório)
     rankers: 10
     rank_interval: 300
     personal_win_score: 10
     personal_lose_score: -5
     big_rank_difference: 100
     group_win_score_small: 10
     group_lose_score_small: -10
     group_win_score_big_higher: 5
     group_lose_score_big_lower: -5
     group_win_score_big_lower: 20
     group_lose_score_big_higher: -20
   ```
   Os valores padrão do original vêm do `setting.txt` (`GrandPrix:*`) e são 0 se ausentes; os acima são sugestão.
   O `config.yml` do repositório vem com `rank_interval: 30` para testar (o original usa 300).
2. Uma config só (`config.yml`): o servidor Grand Prix é o índice 1 da lista `gameservers`. Suba com `game.py 1`
   (bat: `servidor-game-grandprix.bat`); o log fica em `logs/game-1-*.log`.
3. Grupos e jogadores no banco. O `db/gbwc.sql` não traz grupos; exemplo com as contas de teste `mario` (grupo 1)
   e `test` (grupo 2):
   ```sql
   INSERT INTO GrandPrix_Group (Category, ScoreOnCalc, Rank, RankOld, Win, Lose) VALUES ('1','0','0','0','0','0');
   INSERT INTO GrandPrix_Group (Category, ScoreOnCalc, Rank, RankOld, Win, Lose) VALUES ('2','0','0','0','0','0');
   INSERT INTO GrandPrix_Personal (User, Score, Rank, RankOld, Win, Lose, Category) VALUES ('mario', 0, 0, 0, 0, 0, '1');
   INSERT INTO GrandPrix_Personal (User, Score, Rank, RankOld, Win, Lose, Category) VALUES ('test', 0, 0, 0, 0, 0, '2');
   ```
   Para trocar de grupo: `UPDATE GrandPrix_Personal SET Category='2' WHERE User='mario'`.

## Ranking (desempenho em qualquer banco)
`GrandPrixRepository.refresh_ranks`: `SELECT User ... ORDER BY Score DESC` e um único `executemany`
(`RankOld=Rank, Rank=posição`) numa transação. Só SQL comum a SQLite/MySQL/PostgreSQL (sem window function nem
`UPDATE ... FROM`). Roda no máximo a cada `rank_interval`; o 0x1101 responde da memória. Com muitos jogadores,
crie índice em `GrandPrix_Personal(Score)`; o `UNIQUE (User)` o `init_db.py` já cria.

## Layout 0x1101 (cliente v440 0x4caeb1)
`u16 rtc(0)` + `u16 nGrupos` + n × 24 [6 × i32] + `u16 nPessoas` + n × 36 [6 × i32 + Nickname 12]
+ `u8` tem meu grupo + 24 + `u8` tenho registro + 24 (mesma ordem do registro pessoal, sem nick).

| Registro | Ordem que o servidor manda (WCS1) |
|---|---|
| grupo | `Rank, Rank−RankOld, Category, Pontos, Win, Lose` |
| pessoa | `Rank, Rank−RankOld, Category, Score, Win, Lose` + apelido |

- Essa é a ordem que o v495 lê ([Cliente v495 x v440.md](Cliente%20v495%20x%20v440.md)). A versão anterior deste
  documento, feita pelo leitor do v440, tinha o grupo como `Category, Pontos, Rank, Rank−RankOld, Win, Lose` e a pessoa
  com 0 no 3º campo; a fase WCS1 manda a ordem do v495 também ao v440. **[INCERTO]** como a tela do v440 mostra.
- WCS2 (v584): grupo de 44 bytes e pessoa de 56 (nome de 20 bytes no meio); ver
  [Cliente v584 - pacotes.md](Cliente%20v584%20-%20pacotes.md) e `phase.WCS2.gp_group`.

## Testar
1. `servidor-broker.bat` e `servidor-game-grandprix.bat` (mais `servidor-game.bat` se quiser os dois na lista).
2. Cliente 1 com `mario` (grupo 1), cliente 2 com `test` (grupo 2), ambos em "Gunbound WC Grand Prix".
3. No canal o cliente mostra o painel de Grand Prix no lugar da lista de salas (cliente 0x4fcd09: tipo 2 cria
   outra tela; 0x4fc670: botão 1 manda 0x2140). O ranking (0x1100/0x1101) vem ao abrir.
4. Botão de começar nos dois: console deve mostrar `SVC_ROOM_GRANDPRIX_BEGIN: na fila` duas vezes e a sala
   `GrandPrixRoom` abre para os dois (quem entrou por último é o mestre).
5. Joguem até o fim: no resultado o console grava pontos; abrir de novo o ranking mostra o placar depois de
   `rank_interval` (30 s no `config.yml` do repositório).
Conferir no banco: `SELECT * FROM GrandPrix_Personal; SELECT * FROM GrandPrix_Group;`

## Investigar
- Observado no cliente: a `Category` aparece como código de país (1 = AF, 2 = AL), ou seja, o Grand Prix é
  país contra país; a categoria deve seguir a tabela de países do cliente.
- No 0x3432 o u16 "evento atual" (hoje 0xFFFF) com valor 1 faz o cliente carregar `grandprix.img`; no original
  é o evento sorteado pelo SET_EVENTACTPROB, não ligado à sala de Grand Prix.
- Ordem dos 24 bytes do "eu" (0x4447 no original monta a partir de `Score, Rank, RankOld, Win, Lose`); usamos a
  ordem do registro pessoal.
- O 3º campo do registro pessoal: 0 no original; aqui vai a `Category`.
- Se o cliente espera algum pacote próprio ao fechar a partida (hoje: 0x21F5 + 0x2111) e onde ele abre a tela de
  Grand Prix. Não testado no cliente ainda.
- Uso de `GameOption` do original (dword de opções da sala); aqui só `mode` e `stage`.
