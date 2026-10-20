# Revisão: servidor 2007 do pacote "Season 2 server" x emulador (fase WCS2)

Referências comparadas:
- **Servidor 2007**: `Season 2 server\GunboundServer01\GunBoundServ3.exe` (build 2007-02-05, fora deste repositório).
  É um **WC S1**: só tem os 67 `SVC_*` do S1, nenhum handler do S2. Não é fonte do comportamento do S2; o que ele faz
  vale para o S1, e no WCS2 só como herança do S1 (🟡 sem fonte para o S2). O `Setting.txt` da pasta é de 2021,
  configurado por quem montou o pacote (a faixa de patente 1–40 já é a numeração do S2). `HiddenServer.exe` é o mesmo binário (mesmo sha256), muda só o Setting.txt.
- **server-original**: `server-original\GunBoundServ3` (build 2006, fora deste repositório).
- **Emulador**: `gunbound/game` (fase `WCS2` em `phase.py`, `config.yml`).

O cliente alvo é o v584 (2010). Por isso os opcodes do v584 (jackpot 0x6056, tutorial 0x7012/0x7014, família 0x70xx) **não existem** no original e ficam fora desta comparação (ver [Cliente v584 - pacotes.md](Cliente%20v584%20-%20pacotes.md)).
Este relatório não traz senhas: as linhas `*Password*` dos Setting.txt foram omitidas.

## 1. Opcodes (dispatch do original x handlers nossos)

Todo SVC do dispatcher do original tem handler aqui. O mapa do dispatcher e o que ainda falta (0x1016, SETVERSION
derrubando sessões, os 8 bytes do 0x6028, os S→C de gatilho desconhecido) estão em
[Opcodes do servidor original.md](Opcodes%20do%20servidor%20original.md). O que o cliente manda e trata está em
[Cobertura de pacotes cliente x servidor.md](Cobertura%20de%20pacotes%20cliente%20x%20servidor.md).
Os 0x1004/0x1019/0x101C do cliente não existem no original; aqui são ignorados em silêncio.

## 2. Regras do Setting.txt

Valores: **Pacote** (Setting.txt de GunboundServer01, 2021) / **Hidden** / **2006** (server-original) / **nosso**.

| Chave | Pacote / Hidden / 2006 | Nosso | Lacuna |
|---|---|---|---|
| `FuncRestrict` | 1040399 / 126976 / 2088962 | `function_restrict` no item de `gameservers` (padrão 0; o `config.yml` do repositório não define) e via 0x5124/0x5128 | **alta**: ninguém consulta a máscara fora do STATUS 0x5111. O original usa a máscara para bloquear funções (o efeito de cada bit ainda precisa ser mapeado no binário) |
| `EventActProp0..3`, `EventWriteToLog*`, `EventTreatAsIndex*`, `[EventTrigger:N]` | Pacote: 0/0/100/100; Hidden: 50/100; triggers 10/50/100/300/500 → gold ou avatar | `events` (lista de `(prob, a, b)`) no item de `gameservers` ou via 0x5128; **sem sorteio e sem prêmio por evento** ([Eventos.md](Eventos.md)) | **alta** se quiser os eventos do servidor 2007: falta o sorteio por probabilidade e a entrega dos prêmios do `[EventTrigger]` (G = gold, A = avatar), além do log em `eventlog` |
| `Tank.Hidden.Ratio` | 20 / 100 / 10 | ausente: `roll_tank` (`gunbound/game/room.py`) sorteia uniformemente de 0..TANK_COUNT-1 | **média**: o original dá uma chance (%) de o sorteio "Random" cair nos tanques ocultos. Confirmar no binário quais tanques |
| `GradeLimitFirst/Last` | 1–40 / 1–41 / 20–20 | `grade_min/grade_max` vão ao broker e ao 0x5111, mas **o login não recusa** quem está fora da faixa | **média**: no original é a trava de entrada por patente (servidor de iniciantes etc.) |
| `QuickStartOption` | 283074 (todos) | `quick_mode` só via `/qsopt`, sem valor inicial | baixa: ler do config como valor inicial |
| `QuickStartMan` | 0 / 6 / 1 | `quick_min_players` (padrão 1, `/qsman`): aqui é o tamanho da `QuickStartRoom` criada quando não há sala livre | baixa/média: no original é o mínimo de jogadores da sala para o quick start escolhê-la [INCERTO] |
| `IdleRoomWarnTime` / `IdleRoomCloseTime`, `RoomCloseMsg`, `RoomCloseWarnMsg` | 2280/2220 s (Hidden: menor) | **ausente** | **média**: salas paradas nunca são avisadas nem fechadas |
| `ANU_DROP_GOLD` / `ANU_DROP_GP` | 5000 / 40 | **ausente** | média: prêmio do drop "Anu" (gold/GP). Confirmar no binário quando dispara |
| `ScoreFactor` / `GoldFactor` | 200/200 (2006: 120/120) | `score_factor`/`gold_factor` = 270/230 no config.yml | ok (implementado); só os valores diferem |
| `SuperUserItem` | 204801 | `super_user_item` 204801 | ok |
| `EventUserItem` | 229640 | ausente | baixa: item que marca o "usuário de evento" |
| `MaxRoom` | 200 | constante `MAX_ROOMS = 300` em `gunbound/game/managers/rooms.py` | baixa: tornar configurável |
| `RecommendedMan` | 200 | usado no broker (`gunbound/broker/protocol/server_sorted_list.py`) | ok |
| `NoRoomCreate` (só 2006) | 0 | ausente | baixa |
| `MaxConnection`, `MaxConnectionPerSource`, `SingleSourceMonitor`, `Ban*` | 2048 | `users_max`; sem limite por IP | baixa (anti-flood) |
| `Accept` | lista CIDR | `accept` | ok |
| `VersionFirst/Last`, `ProductVersion` | 1–999 | `version_min/max`, `product_version` | ok |
| `ClientChecksum` | 9fd25ff2 | ausente | baixa (anti-hack) |
| `GrandPrix:*` | ver [Grand Prix.md](Grand%20Prix.md) | `grandprix:` no config | ok |
| `DK:*`, `IpVerifyMail_*`, `IsUseTimerForNProtect` | — | ausentes | ignorar (DK = outra região; mail/nProtect fora do escopo) |

## 3. Banco (DB\gunbound.sql, batch.sql)

O dump do pacote só tem tabelas (nenhuma procedure/function). Comparado com `db/gbwc.sql`:

| Tabela do pacote | Nosso | Observação |
|---|---|---|
| `totalrank` (Id, Nickname, Score, Rank, Grade, Guild, MemberCount, GuildRank) | ausente como tabela; ranks e patentes ficam em `Game`, recalculados por `gunbound/repository/ranking.py` | **média**: é a saída do batch de ranking (inclui `GuildRank`/`MemberCount`). Ligado ao ranking WCS2/guild |
| `batch.gradelimit` (Rank, Grade, Score) e `batch.gamesnapshot` | ausentes | **média**: o batch calcula a patente pela posição no ranking (`gradelimit`). O nosso usa faixa fixa de GP abaixo de 6900 e percentis aproximados acima ([Níveis.md](Níveis.md)), não a tabela do original |
| `rankmax` | ausente | baixa: limite de ranking do batch |
| `guildapli` | ausente | média: pedidos de entrada em guild (lado web) |
| `moneyscoresave`, `iptracing`, `recupepasslog`, `gbevents*` | ausentes | baixa (web/log) |
| `cash`, `chest`, `item`, `gift`, `giftitem`, `giftmsg`, `receipt*`, `buyinfo`, `eventlog`, `accuse`, `grandprix_*` | presentes | ok; `giftmsg` ligado à lacuna do 0x6028 |
| (nossas) `charge_*`, `email_answer`, `report_site`, `do` | só nossas | extras do painel |

## 4. Lacunas priorizadas

1. **Usar `function_restrict`** (já aceito no item de `gameservers`, padrão 0): mapear no binário o que cada bit do FuncRestrict bloqueia.
2. **Eventos do servidor 2007**: sorteio por `EventActProp`, prêmios do `[EventTrigger]`, log em `eventlog`.
3. **Trava de patente no login** (`GradeLimitFirst/Last`).
4. **Sala ociosa**: aviso e fechamento (`IdleRoom*` + mensagens).
5. **Tank.Hidden.Ratio** no sorteio do tanque aleatório.
6. **ANU_DROP_GOLD/GP**: localizar o gatilho no binário e implementar.
7. **Ranking pelo batch**: `gradelimit` (patente por posição) e `totalrank` com `GuildRank`.
8. `QuickStartMan`/`QuickStartOption` como valores iniciais e regra de mínimo de jogadores; `MaxRoom` configurável.
9. 0x6028 (8 bytes + gravação da mensagem), SETVERSION derrubando sessões, 0x1016 (ver [Opcodes do servidor original.md](Opcodes%20do%20servidor%20original.md)).

Não verificado aqui: a semântica exata de FuncRestrict, Tank.Hidden.Ratio, ANU_DROP e QuickStartMan no binário 2007 (inferida pelo nome da chave e pelos documentos existentes). Os itens 1, 5, 6 e 8 pedem uma passada no REA antes de implementar.
