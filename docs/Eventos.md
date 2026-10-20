# Eventos (temáticos e de partida)

Levantado no servidor original (`GunBoundServ3.exe` + `setting.txt`) e no cliente (`GunBound.gme` + `graphics.xfs`).
Há **três** coisas diferentes chamadas "evento".

## 1. Tipo do servidor na lista (broker)
Byte logo após o índice de cada servidor no pacote da lista (`event` em `config.yml`, cliente 0x4f29b6):
| valor | efeito no cliente |
|---|---|
| 0 | normal |
| 1 | servidor de evento: fundo temático na lista (`event_serverlist.img`, "wowlg") |
| 2 | servidor de Grand Prix (automático com `grandprix.enabled`, ver [Grand Prix.md](Grand%20Prix.md)) |

## 2. Evento sorteado na partida (servidor)
É o que o original chama de `EventActProp`. A cada início de partida (original 0x416527):
1. para i = 0..3, se o bit `0x100000 << i` estiver ligado em `FuncRestrict` (features `EVENT1_ENABLE`..`EVENT4_ENABLE`)
   e `rand() % 100 < EventActProp<i>`, o evento i é ativado na sala (log "Event %d is activated at room %d");
2. o índice vai no 0x3432 (u16 depois dos jogadores; 0xFFFF = nenhum).

Chaves no `setting.txt` do original (a mesma seção `[GunBoundXPServ]`), por evento i = 0..3:
| chave | significado |
|---|---|
| `EventActProp<i>` | chance em % por partida |
| `EventWriteToLog<i>` | grava na tabela `EventLog` (Id, Code, AcquiredScore) |
| `EventTreatAsIndex<i>` | índice usado para a pontuação de evento (`Game.EventScore<n>`) |
| `FuncRestrict` | máscara; bits 20..23 ligam os eventos 1..4 |

No original de exemplo: `FuncRestrict = 1040399` (bits 20..23 desligados) e `EventActProp0 = 70`, ou seja, evento
configurado mas desligado.

Os bits de `FuncRestrict` são os mesmos da tabela `features` do `config.yml`: bit 4 avatar, bits 13..19 efeitos de
clima, bits 20..23 eventos 1..4. Exemplo com avatar e os 7 climas ligados: `1040400` (sem evento); somando o bit do
evento: `2088976` (evento 1), `3137552` (2), `5234704` (3), `9429008` (4). Também dá para mudar em tempo real pelo console (0x5128 SET_EVENTACTPROB / 0x5124
FUNCTION_RESTRICT), que no original regrava o `setting.txt`.

### O que o cliente faz com o índice
Ele lê o **`Event14.txt` de dentro do `graphics.xfs`** (não é arquivo solto; o cliente procura nesse pacote).
Uma linha por evento:
```
;Event No.;MB    ;MH    ;MG;MF;FB;FH    ;FG;FF;Mobile;Event;BonusGP;BonusGold;Win Score;Lose Score;use rand
0         32805  98343  -1 -1 40 65578  -1 -1 -1     1     0       0         1         0          1
1..3      -1 (vazios)
```
- MB/MH/MG/MF e FB/FH/FG/FF: avatar forçado (corpo, cabeça, óculos, bandeira) masculino/feminino durante a partida
  (é o "visual temático", ex.: roupa de Natal);
- Mobile: tanque forçado (-1 = livre); BonusGP/BonusGold; Win/Lose Score (vai para `EventScore`); use rand.
- Gráficos do evento: `bulletevent<n>`, `flameevent<n>`, `rayonevent<n>`, `event<n>1800.img`, `event14-<n>.img`;
  com evento 1 ele usa `grandprix.img`.
- Neste cliente só o evento **0** está preenchido. Para criar outro tema é preciso editar o `graphics.xfs`
  (alteração no cliente).

## 3. Tema escolhido no cliente (`ChooseEvent.txt`, também no graphics.xfs)
```
; Event No. ; Command     ; Bonus GP% ; Bonus Gold ; Auto Run ; Background Only ; Event Music
0           gunbound      0           0            N          N                 N
1           cjswoshrdua   0           0            N          Y                 Y
```
Troca fundo/música (ex.: `christmas_event_text.img`). `Command` é uma palavra digitada no cliente que liga o tema;
**[INVESTIGAR]** onde ela é digitada (o leitor fica em 0x408eca; o servidor não participa).

## Não confundir: bônus "+Gold/+GP" do S2 (0x4300)
O v584 tem outro sorteio, separado do `EventActProp`: o **último byte** do 0x3432 (0xFF = nenhum) liga um bônus de
tipo 0..9 e o cliente manda 0x4300 ao ganhá-lo. Chave `bonus_event` (% por partida) no game server WCS2;
implementado em `gunbound/game/protocol/wcs2/bonus.py`. Ver [README-WCS2.md](../README-WCS2.md).

## Situação neste servidor Python
- Item 1 pronto (`event` / Grand Prix).
- Item 2: `function_restrict` e `events` podem ir no item de `gameservers` (o console 0x5124/0x5128 também muda), mas o
  sorteio por partida **não está implementado**: o u16 de evento do 0x3432 sempre vai 0xFFFF. Falta: sortear em
  `room_packets.game_start`, somar `EventScore` e gravar `EventLog` no resultado.
- Item 3 é só do cliente.
