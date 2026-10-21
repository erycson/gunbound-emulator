# Criação do banco

Cada servidor roda **uma versão só** (TH, WCS1 ou WCS2), e o banco é dessa versão. Os seeds e as conversões ficam
separados por versão porque há dados e configurações que só fazem sentido numa delas: o encantamento é do S2, e a
patente usa outra numeração no S2 ([Níveis.md](../Níveis.md)).

## Uso

```bat
python init_db.py <TH|WCS1|WCS2>          # usa database.uri do config.yml
python init_db.py <TH|WCS1|WCS2> <uri>    # ex.: sqlite+aiosqlite:///gbwc.db
```

Use a mesma versão do `phase` dos game servers no `config.yml`. Sem versão, o script mostra a ajuda e não faz nada.

## Passos encadeados

O schema vem de `db/linked.sql` (o do servidor original mais as colunas do emulador) e é o mesmo para todas as
versões. Os dados vêm em passos, um por versão, sempre nesta ordem:

| Passo | Seed | Depois do seed |
|---|---|---|
| TH | `db/gbwc.sql`: itens, loja (`Menu`) e contas de teste. É a base de todas as versões | nada |
| WCS1 | `db/seed/WCS1.sql`: por enquanto vazio (nenhum dado é só do S1) | nada |
| WCS2 | `db/seed/WCS2.sql`: níveis de encantamento (`EnchantLevel`) | patentes convertidas para a escada do S2 (`ranking.migrate_th_to_v584`) |

- `init_db.py TH` roda só o passo TH.
- `init_db.py WCS1` roda TH e depois WCS1.
- `init_db.py WCS2` roda TH, WCS1 e depois WCS2.

Cada seed só entra em **tabela vazia**. Em tabelas que já existem, o script acrescenta as colunas e os índices que
faltam, então dá para rodar de novo depois de atualizar o servidor.

## Versão gravada no banco (`DbVersion`)

Ao terminar, o script grava a versão na tabela `DbVersion` (uma linha, coluna `Phase`).

- **Rodar de novo** só aplica os passos que faltam. Um banco já em WCS2 não recebe nada, e a conversão das patentes
  nunca roda duas vezes.
- **Subir de versão:** `python init_db.py WCS2` num banco WCS1 roda só o passo WCS2. Faça backup antes.
- **Voltar de versão** é recusado ("só dá para ir para a frente").
- **Banco antigo, sem `DbVersion`:** é tratado como WCS1, que era o padrão (patentes -4..19).
- **Game server:** ao subir, avisa no log se o `phase` dele não bate com a versão do banco, ou se o banco não tem versão.

## O que muda entre as versões

| | TH | WCS1 | WCS2 |
|---|---|---|---|
| Patentes no banco | -4..19, admin 20 | -4..19, admin 20 | 1..41, admin 0 |
| Job diário de patentes | RankCalc do BatchGIS | RankCalc do BatchGIS | escada do v584 (GP e posição) |
| `grade_min`/`grade_max` do config | 19 / -4 | 19 / -4 | na numeração do S2 (ex.: 1 / 41) |
| `EnchantLevel` | vazio | vazio | seed do S2 |

As tarefas de fundo de cada versão estão em `Phase.tasks` e a regra de patente em `Phase.rank_rule`
(`gunbound/game/phase.py`). Hoje as três só iniciam o ranking diário, cada uma com a sua regra.

Uma conta nova ganha `TotalGrade` 19 pelo default do schema. No S2 isso é a estrela de prata até o job rodar: ele roda
ao subir o servidor e às 4h.

## Acrescentar um passo ou um dado de uma versão

- **Dado só de uma versão:** ponha o `CREATE TABLE` (para a ordem das colunas) e os `INSERT` no seed dela
  (`db/seed/<versão>.sql`), não no `db/gbwc.sql`. A tabela precisa existir no `db/linked.sql`; tabela que não está
  no schema é ignorada.
- **Conversão de dados ao entrar numa versão:** uma função `async def passo(conn)` no `init_db.py`, ligada ao passo em
  `STEPS`. Ela roda uma vez só, porque o `DbVersion` registra o passo.
- **Versão nova:** acrescente-a em `VERSIONS` e em `STEPS` (no fim, porque a ordem é a da cadeia), crie o seed e a
  fase em `phase.py`.

## Limites

- Itens e loja (`Menu`, `Item`, `avatar_table`) são os mesmos nas três versões, todos no seed do TH. Para alinhar com
  o XFS de um cliente, use `tools/xfs_sync/item_sync.py` com o XFS daquela versão.
- Itens próprios do S2 (selos, tickets e outros 700xxx, nas tabelas `ex3`/`ex4`) e os pacotes ficam fora do
  seed: rode `tools/xfs_sync/set_sync.py --xfs <GunBound.xfs do v584>` (senha em `GB_SOLFS_PASSWORD`). Sem eles a
  compra é recusada com "menu N não existe" (Message Code 203 no cliente).
- Só para a frente. Para voltar, restaure o backup.
