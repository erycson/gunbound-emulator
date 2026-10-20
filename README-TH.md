# GBWC EmuServer: GunBound Thor's Hammer (TH)

O que é próprio do TH. O que vale para todas as versões está no [README principal](README.md).

| Cliente | Fase no `config.yml` | ProductVersion no login |
|---|---|---|
| TH v404 (2005) | `phase: "TH"` | `0x00628B68` |

O TH é a base do protocolo: as fases WCS1 e WCS2 herdam dele e só mudam o que difere
(`gunbound/game/phase.py`). Comparação detalhada com o v440 em
[docs/Cliente TH v404 x v440.md](docs/Cliente%20TH%20v404%20x%20v440.md).

## Configuração própria do TH

- **Lista de servidores:** o TH lê o 0x1102 com outro layout (13 bytes no fim de cada servidor). Ligue
  `broker.th_port` no `config.yml` (ex.: `8373`) e aponte o `Port=` do `GunBound.ini` do TH para essa porta.
- **Amigos:** `BuddyIP` e `BuddyPort` (padrão 8352) no `GunBound.ini`.
- **Contas GM e Buddy:** com o jogador local GM (`TotalGrade` 20), o cliente TH ignora os avisos de amigo
  (entrou, saiu, pedido aceito). Não é falha do servidor: teste os amigos com contas sem GM.

## Diferenças de protocolo em relação ao WC

| Ponto | TH | WC (S1/S2) |
|---|---|---|
| País | não existe | patentes + `CountryGrade`/`Country` |
| 0x1012 login | sem `CountryRank`; bloco cifrado em +0x51 | com `CountryRank`; bloco em +0x59 |
| 0x2105 jogador no detalhe da sala | 0x19 bytes | 0x1E (S1) / 0x22 (S2) |
| 0x2103 lista de salas | sem o byte extra | 1 byte a mais |
| 0x6001 baú | nada depois do 3º flag | `Recovered` (S1), + nível de encantamento e u32 (S2) |
| Resposta ao `/kick` (0x3150) | 0x3151 | 0x315F |
| Sair da sala | 0x2000 (volta ao canal) | 0x3001 |
| Grand Prix (0x2140/0x2141) | só registra atividade | fila do Grand Prix |

Opcodes que o TH não manda: 0x3001, 0x2130 (entrada rápida), 0x1090 (dados do cliente), 0x6004/0x6008/0x6030
(presentes do WC) e 0x101C.

## Opcodes só do TH

| Opcode | Status | Notas |
|---|---|---|
| Broker 0x1101 lista por índice | ✅ | aba dos servidores dos amigos; até 16 índices |
| Broker 0x1102 no layout do TH | ✅ | precisa de `broker.th_port` |
| 0x2140 / 0x2141 | ✅ | só registram atividade (o TH não tem Grand Prix) |

O TH não desenha marca de amigo nas linhas da lista de servidores: usa a localização dos amigos (P2P c051 pelo
Buddy) só para montar o 0x1101 da aba de servidores dos amigos.

## Comandos

### GM (chat)

Os comandos de GM do [README principal](README.md#comandos-de-gm-no-chat-autoridade--99-userauthority) valem no TH.
Para calar alguém use `/silence nick segundos`: no TH, `/mute` é tratado pelo próprio cliente (lista de ignorados).

### Tratados pelo próprio cliente TH

| Comando | O que faz |
|---|---|
| `/h`, `/help`, `/guide` | lista de comandos (local) |
| `/to`, `/m`, `/message` ID msg | cochicho pelo Buddy |
| `/kick apelido` | mestre expulsa (0x3150) |
| `/go N` | página N da lista de salas (0x2100) |
| `/mute`, `/mutelist`, `/loudall`, `/loud` | lista de ignorados (local); `/loud` tira da lista (só o TH tem) |
| `/key`, `/ipconfig`, `/quit`, `/exit` | locais |
| `/clear`, `/logging` | P2P entre os jogadores da sala |
| `/<evento>` (`ChooseEvent.txt`) | mestre liga um evento na sala (0x3101): o servidor grava o settings cru e repassa, como o original; quem interpreta o evento é o cliente |
