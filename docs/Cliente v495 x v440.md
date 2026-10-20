# Cliente v495 x v440 (opcodes e layouts)

Levantamento feito só por leitura no `GunBound.gme` desempacotado do v495 (sha256 `b245c935…`) contra o v440
(sha256 `15e4b4a2…`), com capstone e REA/Ghidra. O v495 e o v440 usam a mesma fase **WCS1** (`phase.py`), que aceita o
ProductVersion 0x04FCCB1C e manda o 0x1101 no layout do v495.

## Login
- 0x1010: o layout é igual. O ProductVersion muda para **0x04FCCB1C**, o mesmo do v584 com chave Brasil.
  Aceito na fase WCS1.
- Pré-despacho (`v440 0x445d70` / `v495 0x448e80`): os opcodes cifrados e os que têm RTC conferido são iguais.
  O v495 tem 3 mensagens de RTC novas: 0x1002, 0x2002 e 0x2003. O servidor não manda nenhuma delas.

## Opcodes
Envio C→S: a função de envio é `v440 0x445b40` / `v495 0x448c50`, mais as gravações diretas em `this+0x9c`.
Recepção S→C: árvore de comparações em `v440 0x40e9c9` / `v495 0x40f042`, varrida para todos os valores.

| | v440 | v495 |
|---|---|---|
| C→S | 0x1019, 0x101C | 0x1016 (REP_AUTHDWORD, resposta ao anti-hack) |
| S→C | 0x1018, 0x101B | 0x1015 (desafio anti-hack), 0x9003 |

Tudo o que não está na tabela é igual nas duas versões.

**Risco:** o game server manda **0x1015** (`LoginResp.success_token`) quando o cliente fica 300 s sem autenticar
(`client.py`). O v440 ignorava esse pacote. O v495 trata o 0x1015 e responde 0x1016, e o servidor não tem handler
para 0x1016 (está comentado em `services.py`). Não testei o que acontece.

## Layouts conferidos
| Pacote | Resultado |
|---|---|
| 0x201F chat | igual: tamanho em +0xD, texto em +0xE |
| 0x2111 entrar na sala | cabeçalho e bloco por jogador iguais: slot, apelido 12, gênero, IP/porta x2, 3 bytes, time, guild 8, 4 patentes |
| **0x1101 ranking do GP** | **mudou o significado dos campos**, o tamanho é o mesmo (veja abaixo) |
| 0x3432 início da partida | igual (leitor `v440 0x4eced2` / `v495 0x4f97dc`): mesma sequência de campos até o eco do 0x3430 |
| avatar no 0x2111 | igual: u16 + u32 por item, depois 1 byte |
| 0x3010 | igual: o handler da sala só lê o byte do slot |

### 0x1101 no v495
O tamanho no fio é o mesmo: grupo de 24 bytes, pessoa de 36 bytes (24 + apelido 12) e o bloco "meu".
A tela nova (`v495 0x50a700`) é uma tabela de 6 colunas e lê assim:
- **+0x4 tem o sinal invertido** ao receber (`if (x) x = -x`), no grupo, na pessoa e no "meu";
- **+0x8 é índice de texto** (nome do grupo pela tabela de strings `0x447b10`), no grupo e na pessoa;
- colunas: +0, +4, +8 (nome), +0xC, +0x10, +0x14.

A WCS1 manda o grupo como `[Category, Pontos, Rank, Rank-RankOld, Win, Lose]` e a pessoa como
`[Rank, Rank-RankOld, 0, Score, Win, Lose]`. No v495 o grupo fica com as colunas trocadas (Pontos negado, Rank lido
como nome) e a pessoa mostra o nome do grupo 0. A ordem provável no v495 é
`[Rank, Rank-RankOld, Category, Pontos, Win, Lose]`, igual à do v584 sem o nome de 20 bytes. A WCS1 manda assim.
A pessoa agora leva a Category em +8, em todas as fases (antes ia 0). Falta conferir na tela do jogo.
