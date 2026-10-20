# Game

Dados de jogo de cada conta: perfil, patentes, ranking, gold e configurações. Uma linha por `User.Id`
([User.md](User.md)). Estrutura completa em `db/linked.sql` (a do servidor original + as colunas do S2).

## Colunas

| Coluna | Tipo | Padrão | Uso |
|---|---|---|---|
| `Id` | varchar(16) | | chave; igual a `User.Id` |
| `Country` | int unsigned | 28 | país (só WC; vai depois das patentes) |
| `NickName` | varchar(12) | | apelido; `UNIQUE` criado pelo `init_db.py` |
| `Guild` | varchar(8) | `''` | guild |
| `MemberCount` | smallint | 0 | membros da guild (vai no 0x1012) |
| `Money` | int unsigned | 0 | gold |
| `EventScore0`, `EventScore1` | int | 0 | pontuação de evento (vão no 0x1012) |
| `EventScore2` | int | 0 | S2: fichas do caça-níquel (0x7110/0x7113) |
| `EventScore3` | int | 0 | S2: progresso do tutorial (0x7012/0x7014) |
| `AvatarWear` | bigint | 0 | [INCERTO] avatar vestido no original; o emulador usa `Chest.Wearing` |
| `Prop1`, `Prop2` | varchar(201) | | [INCERTO] sem uso no emulador |
| `AdminGift` | smallint | 0 | [INCERTO] sem uso no emulador |
| `TotalGrade`, `SeasonGrade`, `CountryGrade` | tinyint | 19 | patentes ([Níveis.md](../Níveis.md)); 20 = GM |
| `TotalScore`, `SeasonScore` | int unsigned | 1000 | GP total e da temporada |
| `TotalRank`, `SeasonRank`, `CountryRank`, `GuildRank` | int unsigned | 0 | posições no ranking (job diário em `gunbound/repository/ranking.py`) |
| `AccumShot`, `AccumDamage` | int unsigned | 0 | tiros e dano acumulados (vão no 0x1012) |
| `NoRankUpdate` | tinyint(1) | 0 | [INCERTO] no original, tira a conta do ranking; o emulador não lê |
| `ClientData` | varbinary(100) | | dados do cliente, devolvidos no 0x1090 → 0x1091; `[0:2]` = tanques primário e secundário (0x3200). Vazio: mandar -2 (`0xFE`) no 1º byte |
| `StageRecords`, `MobileRecords` | varbinary(161) | | [INCERTO] vitórias/derrotas por mapa e por mobile (tanque); o emulador lê as tabelas `StageRecord`/`MobileRecord` |
| `LastUpdateTime` | datetime | | última atualização |
| `GiftProhibitTime` | datetime | | até quando não pode dar presente |
| `DiscountPoints` | int | 0 | S2: pontos de desconto da loja (0x7118; 50 = −20%, 100 = −50%) |
| `RenaPoints` | int | 0 | S2: saldo da Rena (0x7124; 100 por sorteio) |

`DiscountPoints` e `RenaPoints` não existem no banco original. Em banco antigo, rode `python init_db.py`: ele
acrescenta as colunas e os índices que faltam. O cliente não mostra de onde vêm esses pontos; hoje só por SQL.

## Índices

- `PRIMARY KEY (Id)`
- `INDEX (Guild)`
- `UNIQUE (NickName)` (criado pelo `init_db.py`; com apelidos repetidos o script só avisa e segue sem o índice)
