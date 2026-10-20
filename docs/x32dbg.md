# Anotações sobre x32dbg

## Logs úteis (breakpoint com log)

| Binário | Endereço | Log | Mostra |
|---|---|---|---|
| `GunBoundServ3.exe` | `0043DA2D` | `{utf8@ebp}` | consultas SQL (lista em [Database/Consultas do servidor original.sql](Database/Consultas%20do%20servidor%20original.sql)) |
| `BuddyServ2.exe` | `0041F1AE` | `{utf8@ecx}` | consultas SQL |
| `GunBound.gme` | `00401A03` | `XFS2: {utf8@[ebp + 8]}` | arquivos `.xfs` carregados |

## Patch do cliente: estabilizar o drag

| Endereço | Original | Novo |
|---|---|---|
| `004DC54A` | `83 C0 02` (`add eax, 2`) | `90 90 90` (nop) |

**[INCERTO]**: não anotamos em qual versão do cliente esse endereço vale; confira os bytes antes de gravar.
