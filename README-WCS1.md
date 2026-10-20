# GBWC EmuServer: GunBound World Champion Season 1 (WC S1)

O que é próprio do WC S1. O que vale para todas as versões está no [README principal](README.md).

| Cliente | Fase no `config.yml` | ProductVersion no login |
|---|---|---|
| WC S1 v440 | `phase: "WCS1"` | `product_version` do config |
| WC S1 v495 (BR) | `phase: "WCS1"` | `0x04FCCB1C` (o mesmo do v584 com chave Brasil) |

Comparação v495 x v440: [docs/Cliente v495 x v440.md](docs/Cliente%20v495%20x%20v440.md).

## O que o S1 traz em relação ao TH

- **País:** `CountryGrade` e `Country` depois das patentes; `CountryRank` no 0x1012 (bloco cifrado em +0x59).
- **Grand Prix:** fila (0x2140/0x2141) e ranking no 0x1101. O v495 lê o grupo com outra ordem de campos
  (`[Rank, Rank-RankOld, Category, Pontos, Win, Lose]`). Ligue com `grandprix.enabled` no servidor.
- **Presentes do WC:** 0x6004 (recebidos), 0x6008 (aceitar/recusar) e 0x6030 (comprar presente).
- **Sala:** entrada rápida 0x2130 e saída 0x3001; o `/kick` responde 0x315F.
- **Layouts:** 0x2105 com 0x1E bytes, 0x2103 com 1 byte a mais, 0x6001 com `Recovered` (u8).
- **0x1090** dados do cliente.

## Opcodes do S1 (e do S2) que o TH não tem

| Opcode | Status | Notas |
|---|---|---|
| 0x1090 dados do cliente | ✅ | |
| 0x2130 entrada rápida, 0x3001 sair | ✅ | sem sala livre cria "QuickStartRoom" (0x2132); falha 0x2131 RTC 8 |
| 0x6004 / 0x6008 presentes recebidos / aceitar | 🟡 | recusar devolve o valor a quem recebeu, não a quem enviou |
| 0x6030 comprar presente | ✅ | |
| 0x1100 lista do Grand Prix, 0x2140 / 0x2141 fila | 🟡 | colunas do ranking deduzidas por analogia |
| Marca de amigo na lista de servidores | ✅ | o cliente desenha um ícone na linha do servidor onde há amigo online; vem do P2P c051 repassado pelo Buddy, com o u16 índice do 0x1102. Só aparece ao voltar para a lista (o Buddy conecta no 1º canal). Detalhes em [BuddyServ.md](docs/BuddyServ.md) |

## Comandos

### GM (chat)

Os comandos de GM do [README principal](README.md#comandos-de-gm-no-chat-autoridade--99-userauthority) valem no S1.
Só no S1 o `/mute nick segundos` chega ao servidor e funciona como `/silence` (no TH e no S2 o cliente usa `/mute`
para a lista de ignorados).

### Tratados pelo próprio cliente S1

| Comando | O que faz |
|---|---|
| `/h`, `/help`, `/guide` | lista de comandos (local) |
| `/to`, `/m`, `/message` ID msg | cochicho pelo Buddy |
| `/kick apelido` | mestre expulsa (0x3150) |
| `/go N` | página N da lista de salas (0x2100) |
| `/mute nick segundos` | não é do cliente: vai ao servidor e funciona como `/silence` (a lista de ignorados do S1 é uma janela, sem comando) |
| `/key`, `/ipconfig`, `/quit`, `/exit` | locais |
| `/clear`, `/logging` | P2P entre os jogadores da sala |
| `/<evento>` (`ChooseEvent.txt`) | mestre liga um evento na sala (0x3101); o modo é mantido e o evento ignorado |
