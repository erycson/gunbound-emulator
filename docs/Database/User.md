# User

Conta de login. Estrutura em `db/linked.sql` (mesma do servidor original); contas de teste em `db/gbwc.sql`.
O `Id` liga com `Game.Id` ([Game.md](Game.md)).

## Colunas usadas pelo emulador

| Coluna | Uso |
|---|---|
| `Id` | login (chave) |
| `User` | nome de usuário; índice criado pelo `init_db.py` |
| `Nickname` | apelido; `UNIQUE` criado pelo `init_db.py` |
| `Password` | senha conferida no 0x1010 (texto puro ou o md5 que o NyxLauncher manda) |
| `Gender` | 0 = homem, 1 = mulher |
| `Authority` | permissão de GM (abaixo) |
| `RestrictTime` | banimento: o login recusa enquanto a data não passar; gravado pelo `/ban` |

`Status`, `MuteTime`, `Authority2`, `E_Mail`, `Country` e `User_Level` são lidos ou existem no schema, mas o emulador
não usa (o `/silence` não grava `MuteTime`: o bloqueio é só no cliente, pelo 0x1040).

## Authority

| Valor | O que libera |
|---|---|
| ≥ 98 | console de admin: `STATUS`, `MOTD`, `BCM` e o monitor de canal (0x2020) |
| ≥ 99 | comandos de GM no chat (0x5100) e o resto do console (0x5116–0x512C) |

O admin de teste do `db/gbwc.sql` tem 100. Lista de comandos: [Comandos GM.md](../Comandos%20GM.md).
