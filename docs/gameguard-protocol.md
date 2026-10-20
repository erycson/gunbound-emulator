# Anti-hack (GameGuard / HackShield): protocolo e estado no emulador

Fontes:
- análise estática dos clientes em `clientes\` (TH v404, v440, v495, v548, v584);
- servidores originais 2006 (GunBoundServ3 f176515f…) e 2007 (7e954d73…). Os dois são do **WC S1**: o 2007 é um build
  de 05/02/2007 que veio no pacote "Season 2 server", só com os handlers do S1. Não há servidor original do S2;
- relatório de outra IA (20/10/2026, `../../gg-server-emu/RELATORIO-GAMEGUARD-2026-10-20.md`): transporte CSAuth2 e
  primeira pergunta do GameMon v584, por emulação Unicorn de trechos do servidor 2007, do GameMon e da `ggauth50`.
  Marcado **[R]**. Este projeto não reproduziu esses testes.

Nada foi executado por este projeto.

"Em claro" nas tabelas quer dizer **sem a cifra da sessão** do jogo. No GameGuard os 16 bytes ainda passam pela
transformação do CSAuth2 (ver o fluxo).

Legenda: **[O]** observado no binário · **[I]** inferido · **[?]** desconhecido · **[R]** do relatório de outra IA.

## Resumo

| Cliente | Proteção | Pergunta S→C | Resposta C→S | Resultado S→C | Estado no projeto |
|---|---|---|---|---|---|
| TH v404 | HackShield 3.3 (EHSvc) | 0x1018, 48 B | 0x1019, 24 B em claro | 0x1017 RTC 0 → probe UDP [O] | patch NoHS; a resposta é hash do próprio GME (patchado) |
| WC S1 v440 | HackShield 4.0 (EHSvc) | 0x1018, 160 B / 0x101B, 20 B | 0x1019, 56 B / 0x101C, 20 B em claro | 0x101A ou 0x1017 RTC 0 → probe UDP [O] | patch NoHS; com a DLL ausente responde erro 3 |
| WC S1 v495 | GameGuard 2007 | 0x1015, 16 B em claro | 0x1016, 16 B em claro (CSAuth2) | 0x1017 RTC 0 | patch NoGG; hook `portable.dll` (ver abaixo) |
| WC S2 v548 | GameGuard 2009 ("GunBoundBR") | 0x1015, 16 B | 0x1016, 16 B em claro | 0x1017 RTC 0 | patch NoGG (`0x40a7f0`) |
| WC S2 v584 | GameGuard 2009/2010 ("GunboundEng") | 0x1015, 16 B | 0x1016, 16 B em claro | 0x1017 RTC 0 | patch NoGG (`0x40a5df`, `0x40a639`) |

**Nenhum cliente da pasta `clientes\` tem a proteção ativa.**
- Com NoGG, o singleton do GameGuard (`DAT_0091d788` no v584) fica 0: um 0x1015 não gera 0x1016.
- Com NoHS, o v440 responde erro e o TH responde o hash do GME patchado.

## Fluxo GameGuard (v495 / v548 / v584)

1. **[O]** C→S 0x1010 → S→C 0x1012 OK. O handler do 0x1012 (v584 `0x514504`) chama SendUserID no GameMon (IPC 0x613) com os 12 bytes do corpo a partir do byte 6.
2. **[O servidor 2007]** S→C **0x1015**: 16 bytes vindos do `GetAuthQuery` do ggauth embutido.
   - Vai logo depois do 0x1012.
   - **[R]** Não é o `GG_AUTH_DATA {u32 index, u32 v1, u32 v2, u32 v3}` cru. O servidor 2007 o transforma em `0x4430C0`:
     XOR em cada DWORD e dois blocos Blowfish intercalados (DWORDs 0/2 e 1/3). A chave Blowfish é inicializada em
     `0x4432B0` com dados do próprio executável. A resposta é desfeita em `0x443120`, com outras constantes.
   - **[R]** O GameMon v584 desfaz a pergunta em `0x48163C` e transforma a resposta em `0x4815C0`. O cliente (GME) só
     copia os 16 bytes.
   - Codec offline: `../../gg-server-emu/tools/csauth2_codec.py`. Lê as constantes do `GunBoundServ3.exe` S2 (confere o
     sha256) e só converte o transporte: não gera nem valida respostas.
   - **Sem a cifra da sessão**: a recepção do v584 (`0x455c10`) só decifra 0x1032, 0x1033, 0x201F, 0x3432, 0x4102, 0x4106, 0x4410 e 0x6002.
3. **[O]** O cliente (handler global v584 `0x40f740`, caso `0x40faf9`) copia 16 bytes do corpo **sem conferir o tamanho** e chama Auth2 (IPC 0x619).
4. **[O]** O GameMon devolve o evento 1017 (CHECK_CSAUTH2). O callback (v584 `0x41925a`) manda C→S **0x1016** com 16 bytes **em claro** (22 bytes no fio).
   - O caminho 1016/CSAuth1 (`0x419394`) manda um DWORD **cifrado** com a chave de sessão, também 22 bytes no fio.
   - Pelo tamanho os dois são indistinguíveis.
5. **[O servidor 2007]** `CheckAuthAnswer` falhou → o handler retorna 0 e a conexão cai.
   OK → `sessão+0x242c = agora` e S→C **0x1017 RTC 0**.
6. **[O]** No v584, 0x1017 RTC 0 na cena GateWater (`0x5141c0`):
   - manda por UDP os 4 bytes que vieram no 0x1012 (byte 2) para IP:porta do game server;
   - muda a cena para o estado 7.

   RTC ≠ 0 não faz nada. **Um 0x1017 RTC 0 falso tem efeito colateral no cliente.**

### Repetição e prazo (servidor 2007, `0x412770`) [O]

- A checagem é **preguiçosa**: a cada pacote de quem está logado com Authority < 98 (menos o próprio 0x1016).
- Mais de 200 s desde a última resposta boa sem pergunta feita → novo 0x1015.
- Mais de 300 s sem a 2ª pergunta → outro 0x1015.
- Mais de 600 s sem resposta boa → derruba.
- Não há timer no 2007: quem fica parado não cai até mandar algo.

O servidor 2006 usava CSAuth1:
- 0x1015 com u32;
- 0x1016 com 12 bytes cifrados;
- prazos 300/600 s.

**Não vale para os clientes GameGuard acima.**

### Negociação e primeira pergunta [R]

- O `csauth2.cfg` do 2007 lista `50 51 52`. O `0x441C60` carrega o primeiro como padrão e o `0x4424F0` inicia cada sessão
  com ele: a primeira pergunta sai da **`ggauth50`**, com `{0, 0, 0, 0x10050}`. (A conta anterior, `{0, 0, 0, 0x10052}`,
  era da `ggauth52` isolada, que não é a padrão.)
- O wrapper do S2 (`0x442780`) escolhe a DLL pelo **primeiro DWORD da resposta**:
  - igual: mantém;
  - maior, na pergunta de índice 0: troca para a DLL com essa versão;
  - menor: erro 0xC. Não há downgrade.
- **Ordem das camadas** (pergunta `0x4425D0`, resposta `0x442780`):
  1. `GetAuthQuery` → cópia **interna** em objeto+0x18;
  2. `PrtcEncryptQuery` só se o 1º DWORD interno ≠ 0;
  3. sempre `0x4430C0`;
  4. fio (0x1015).

  Na volta, a ordem se inverte: fio → sempre `0x443120` (XOR diferente do da pergunta) → `PrtcDecryptAnswer` só se o
  1º DWORD interno ≠ 0 → `PrtcCheckAuthAnswer` com a pergunta **interna**, nunca com a do fio. Na `ggauth52`,
  Encrypt/Decrypt são um stub que devolve 0. Isso não vale para outras DLLs só pelo nome do export.
- O terceiro DWORD da primeira resposta traz a versão do GameGuard em `AAAAMMDDRR`. O wrapper aceita os anos 2003..2010
  e aplica um mínimo global. A data de 2008 das DLLs **não** prova que o GameGuard de 2009 é recusado.
- O GameMon v584 (`0x481822`) põe **0x10050** no primeiro DWORD: fala o protocolo da `ggauth50`.
- O índice da pergunta escolhe um de 501 casos (0..500). O caso 0 (`0x4849B6`) devolve
  `{0x10050, 0xECD7A61C, …}`, com os dois últimos DWORDs vindos de estado do GameMon.
- Teste offline (Unicorn): o `PrtcCheckAuthAnswer` da `ggauth50` aceitou (0) as respostas dos casos **0 e 346**, obtidas
  pelo callback original do GME por IPC (o desafio entrou pelo wrapper Auth2, não pela rede). Com um byte alterado, deu
  12 e 13. Os outros 499 casos, os prazos e o GameGuard ativo pela rede não foram testados. O v495 e o v548 não foram
  analisados.
- O GameMon ainda fecha com código 1 por volta de 45 s, mesmo sem pergunta. A causa não foi verificada.
- **[O servidor 2007]** `GGAuthUpdateTimer()` (chama o `PrtcUpdateTimer` de **todas** as ggauth) roda a cada 300 s:
  timer de 300000 ms com callback `0x407490`, criado em `0x4066ea`. É estado global das DLLs (na `ggauth50`,
  `0x1000E7C0` lê `GetSystemTime` e grava o índice em `0x1001AF04`). Não é o prazo de cada sessão (200/600 s).
- **Armadilha:** o `PrtcCheckAuthAnswer` da `ggauth52` devolve 0 quando não há pergunta pendente, sem olhar a resposta.
  O `anticheat.py` já recusa `sem_pergunta_pendente` antes do validador; uma ponte para o ggauth tem de manter isso.

### Desconhecido [?]

- Se o GameMon de 2010 aceita uma pergunta no formato antigo via Auth2.
- Prazos internos do GameMon.
- O que o GameMon faz com o 0x1015 de 4 bytes que este emulador mandava antes. Removido: o cliente copiava 16 bytes e os 12 finais eram lixo do buffer.
- Comportamento do cliente sem nenhum 0x1015: no código do jogo, nada acontece (sem timeout).

## Fluxo HackShield (TH v404 / v440)

- **[O] v440** (EHSvc 4.0.0.1):
  - S→C 0x1018 (160 B) → ordinal 12 → C→S 0x1019 (56 B em claro);
  - S→C 0x101B (20 B) → ordinal 13 → C→S 0x101C (20 B em claro);
  - em falha, o mesmo opcode com u32 de erro **cifrado** (16 B no fio).
  - **[I]** Os ordinais 12/13 parecem `_AhnHS_MakeAckMsg` / `_AhnHS_MakeGuidAckMsg`, pelo tamanho.
- **[O] TH v404**: S→C 0x1018 (48 B) → `0x521810` → C→S 0x1019 (24 B em claro). A resposta é calculada sobre o **próprio arquivo GME** na faixa pedida e funciona mesmo com NoHS (hash do GME patchado).
- **[?]** Nenhum servidor original do projeto fala HackShield: os servidores 2006 e 2007 não têm 0x1018/0x1019/0x101B/0x101C. Validação, opcode de resultado e prazos: **sem fonte**.

## Implementação no emulador (`gunbound/game/anticheat.py`)

Configuração **global** no topo do `config.yml` (`anticheat.provider` / `anticheat.mode`). Um `anticheat:` dentro de um
game server sobrepõe o global. Ligar ou não é decisão de configuração, não depende da versão do cliente.

| mode | O que faz |
|---|---|
| `off` (padrão) | Não manda 0x1015/0x1018/0x101B nem 0x1017. Respostas que chegarem só são registradas (`result=ignorado_off`). |
| `observe` | Registra cada resposta: tamanho, sha256[:8], tempo desde a pergunta e veredito. Nunca manda 0x1017 e nunca derruba. Sem validador, o veredito é `nao_verificado`. |
| `capture` | Só `gameguard`. Manda uma vez o 0x1015 fixo de `capture_query` (16 bytes no formato do fio; ex.: `../../gg-server-emu/capture-query-protocol50.bin`) e grava o par em `capture_out` (JSON por linha, hex, sem usuário). Não valida, nunca manda 0x1017, não repete e não derruba. Arquivo ausente ou fora de 16 bytes: o servidor não sobe. |
| `required` | Exige validador confirmado. **Hoje não existe nenhum**, então o servidor não sobe (`ValueError` em `GameServer.start`). |

Com validador (só em `required`/`observe`):
- pergunta logo depois do 0x1012;
- uma pergunta pendente por opcode;
- resposta só vale uma vez (replay = `sem_pergunta_pendente`);
- tamanho fora do perfil = `tamanho_invalido`;
- opcode de outro provider é recusado;
- 0x1017 RTC 0 **só depois de `Validator.check()` verdadeiro**;
- nova pergunta 200 s depois (`anticheat.requery` no `config.yml`);
- prazo de 600 s (`anticheat.deadline`; timer asyncio, cancelado em `ClientConnection.close()`).

Os dois prazos são só configuração e só correm com o anti-hack ligado: `mode: off` não arma nada, e o prazo só é
armado em `required`.

Em `required`, qualquer falha derruba a conexão, como o servidor 2007.

Contrato do validador (`Validator`):
- uma instância por sessão, porque guarda a DLL escolhida na negociação (objeto+0x00 no 2007);
- `query()` devolve `Query(internal, wire)`;
- `check(exchange, internal, answer)` recebe a pergunta **interna** e o corpo cru do 0x1016;
- o estado global das DLLs (`UpdateTimer` de 300 s) fica com o validador, não com a sessão.

**Por que não há validador:**
- o algoritmo CSAuth/CSAuth2 é do fornecedor (ggauth50/51/52.dll do servidor 2007, exports `PrtcGetAuthQuery`, `PrtcCheckAuthAnswer`…);
- não foi portado. Só o transporte foi portado, fora do servidor (codec offline, acima), e ele sozinho não valida nada.
- falta um par real 0x1015/0x1016 **pela rede**. Os pares 0 e 346 vieram por IPC, e o GameMon dos testes fecha com
  código 1 por volta de 45 s.

O caminho para `required` é executar a `ggauth50` como caixa-preta. A proposta atual **[R]** é emular as instruções
x86 dela em Unicorn, dentro do servidor:
- um worker serializado, dono do estado da DLL, do CRT e do TLS;
- `PrtcGetVersion(1)` uma vez;
- `PrtcUpdateTimer` a cada 300 s na mesma fila;
- falha fechada em qualquer API ou acesso não suportado.

Os detalhes estão em `docs/gameguard-handoff.md`, na "Terceira resposta". Isso é executar código de terceiros, vindo
do pacote "Season 2 server", e depende de autorização do dono do projeto. **Não foi feito.**

Para diagnóstico, a pergunta do fio da `ggauth50` é invertível (`Codec.decode_query`), e
`../../gg-server-emu/tools/check_pair_files.py` confere um par de 16 + 16 bytes. Os dois são offline.

### Logs

Formato:

```
[anticheat] sess=<n> prov=<provider> mode=<modo> step=<start|challenge|answer|result|timeout|disconnect|close> op=0x1016 len=16 sha=<sha256[:8]> dur_ms=<ms> result=<ok|invalido|tamanho_invalido|sem_pergunta_pendente|nao_verificado|ignorado_off|opcode_de_outro_provider>
```

- `sess` é um contador da sessão, sem usuário e sem senha.
- O corpo não vai para o log: compare pelo sha256 da sua captura.
- Na subida: `[anticheat] <nome do servidor>: provider=… mode=…`.

## Vetores

**Não há vetores reais** (par 0x1015/0x1016 gerado por GameGuard ativo): nenhum cliente do projeto tem o GameGuard ligado. Os vetores do relatório **[R]** (`../../gg-server-emu/csauth2-*.json`) são offline, de emulação, não de captura.

Os testes (`tests/test_anticheat.py`) usam um validador **sintético**, só do arquivo de teste: pergunta interna contada, a do fio é ela invertida, e resposta = sha256(pergunta interna)[:16]. Assim o teste falha se alguém passar a pergunta do fio ao check. Nenhuma configuração consegue escolhê-lo.

Cobrem:
- resposta válida;
- resposta alterada;
- resposta truncada;
- replay;
- timeout;
- desconexão cancelando timers;
- isolamento entre duas sessões;
- opcode de outro provider;
- regressão com GG desligado (nenhum 0x1015/0x1017).

Vetores reais devem vir da captura descrita em `docs/gameguard-handoff.md` (cliente GGEmu com GameGuard ativo). Registre a proveniência: binário, sha256, data e qual callback (1016 ou 1017) disparou.

## Hook `portable.dll` no v495 (não é comportamento do servidor)

O v495 do projeto tem uma seção `.port` ("portable.dll", MinGW) que desvia `0x552200`. Sem lib GG, na cena 2, com um flag ligado e servidor 127.0.0.1, ele **injeta um 0x1017 RTC 0 falso** no GateWater. É um atalho local do cliente: não use como referência do servidor.
