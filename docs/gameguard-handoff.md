# Handoff: anti-hack do servidor (GameGuard e HackShield), para quem mexe no cliente

Este documento descreve o que o servidor faz hoje, o que ele espera receber e o que capturar. O protocolo completo, separado em observado, inferido e desconhecido, está em `docs/gameguard-protocol.md`.

## O que o servidor faz hoje

- Configuração **global** no topo do `config.yml`. Vale para todos os game servers; um `anticheat:` dentro de um game server sobrepõe o global. Ligar ou não é decisão de configuração, não da versão do cliente:
  ```yaml
  anticheat:
    provider: gameguard   # none | gameguard | hackshield
    mode: "capture"       # off | observe | capture | required
    capture_query: ../gg-server-emu/capture-query-protocol50.bin
    capture_out: gg-capture.jsonl
  ```
- **off** (padrão): o servidor **não manda 0x1015** e **não manda 0x1017**. O 0x1015 de 4 bytes que saía depois de 300 s parado foi removido.
- **observe**: o servidor só **registra** os 0x1016 (e 0x1019/0x101C) que chegarem. Ele não manda pergunta, porque não tem validador para gerá-la, e nunca responde 0x1017.
- **capture** (só GameGuard):
  - depois do 0x1012 OK, manda **uma vez** o 0x1015 com os 16 bytes de `capture_query`, já no formato do fio;
  - grava o 0x1016 que voltar em `capture_out`, uma linha JSON por par: `query` e `answer` em hex, `dur_ms` e o contador da sessão, sem usuário;
  - não valida, **nunca manda 0x1017**, não repete a pergunta e não derruba ninguém.

  Confira cada par offline com `gg-server-emu/tools/check_pair_files.py`. Ele recebe dois arquivos de 16 bytes; para gerar os dois a partir da linha N do capture:
  ```bash
  python -c "import json,sys; r=json.loads(open('gg-capture.jsonl').readlines()[int(sys.argv[1])]); open('q.bin','wb').write(bytes.fromhex(r['query'])); open('a.bin','wb').write(bytes.fromhex(r['answer']))" 0
  python tools/check_pair_files.py <pasta-originais-S2> q.bin a.bin --version 2009010101 --pending
  ```
  A versão `2009010101` vale só para a resposta inicial do v584. A ferramenta recria o contexto dos testes (flags 3) e não valida uma sessão real. Não serve como autenticação.
- **required**: não sobe. Não existe validador confirmado. O servidor não aceita sucesso fixo.

Para testar o transporte com o GameGuard ativo, use `provider: gameguard` + `mode: "capture"`. Para só escutar, sem mandar pergunta, use `observe`. Nos dois casos, leia os logs `[anticheat]` do game server.

## O que o servidor espera receber (GameGuard, v584)

- C→S **0x1016**: 22 bytes no fio = cabeçalho de 6 + **16 bytes sem a cifra da sessão** (evento 1017 do GameMon, callback v584 `0x41925a`). Os 16 bytes passam pela transformação do CSAuth2 (Blowfish + XOR), não são o `GG_AUTH_DATA` cru.
- Ele chega como `op=0x1016 len=16 sha=<sha256[:8] dos 16 bytes>`. Calcule o sha256 dos 16 bytes que o cliente mandou e compare.
- Se vier pelo caminho 1016/CSAuth1 (DWORD cifrado, `0x419394`), o tamanho no fio é o mesmo. Registre qual callback disparou: o servidor não distingue pelo tamanho.

## Efeito colateral do 0x1017

No v584, 0x1017 com RTC 0 na cena GateWater:
- dispara o probe UDP de 4 bytes (o u32 do 0x1012, byte 2) para IP:porta do game server;
- muda a cena para o estado 7.

O hook `portable.dll` do v495 injeta um 0x1017 falso em 127.0.0.1: isso é do cliente, não do servidor.

## O que capturar (com o GameGuard ativo no GGEmu)

1. **Binário**
   - Bytes em `0x40a5df` (esperado `75 37`).
   - Bytes em `0x40a639` (esperado `81 fe 55 07 00 00 75 0d`).
   - `DAT_0091d788 != 0` depois do init que retornou 0x755.
   - Os endereços valem se o GME desempacotado bater com o dump do v584 do projeto.
2. **Pergunta**
   - Depois do 0x1012 OK, o S→C 0x1015 inteiro: cabeçalho (len 22) + 16 bytes.
   - Horário da chegada.
   - Sem validador, o servidor só manda 0x1015 em `mode: capture`, com a pergunta fixa de `capture_query`.
3. **Resposta**
   - O C→S 0x1016 seguinte: len 22 e corpo de 16 bytes em claro.
   - Qual callback rodou: `0x41925a` (CSAuth2) ou `0x419394` (CSAuth1).
   - Latência entre 0x1015 e 0x1016.
4. **Vetores**
   - Um par 0x1015 + 0x1016 real, com proveniência: sha256 do GME, versão do GameGuard (`GameGuard.ver`), data.
   - Sem esse par, o servidor não tem como validar nada offline.
5. **Robustez**
   - Um 0x1015 de 4 bytes e um 0x1015 corrompido.
   - O GameMon dispara 1014/1001 (ErrorCodeDialog 0x49/0x48)?
   - Guardar os `npgl.erl`/`npgg.erl`.
6. **Depois de um 0x1017 RTC 0**: confirmar o envio UDP de 4 bytes.

## Como conferir a parte do servidor

- Na subida: `[anticheat] <servidor>: provider=gameguard mode=observe`.
- Para cada resposta do cliente:
  ```
  [anticheat] sess=00001 prov=gameguard mode=observe step=answer op=0x1016 len=16 sha=…
  ```
  Em observe sem validador, `result=sem_pergunta_pendente` é esperado, porque o servidor não perguntou.
  Em capture, a primeira resposta sai com `result=capturado out=<arquivo>`.
- Os logs nunca trazem o corpo, usuário ou senha. A correlação é pelo sha256. Só o arquivo do capture guarda os 16 bytes.
- Testes do servidor: `tests/test_anticheat.py` (validador sintético, só de teste).

## As `ggauth` do pacote "Season 2 server" servem? (perguntas para quem analisa o cliente)

O que já se sabe, só lendo arquivos:

- O servidor 2007 da pasta `Season 2 server\GunboundServer01` (um WC S1, build 05/02/2007, sem nenhum handler do S2) traz `ggauth50.dll`, `ggauth51.dll` e `ggauth52.dll` (25/02/2008) e o `csauth2.cfg` com `50 51 52`. **[O]**
  - Exports: `PrtcGetAuthQuery`, `PrtcEncryptQuery`, `PrtcDecryptAnswer`, `PrtcCheckAuthAnswer`, `PrtcUpdateTimer`. **[O]**
  - O executável tem o erro `GGAUTH_INVALID_GAMEGUARD_VER`. **[I]** O servidor escolhe a DLL pela versão do GameGuard do cliente e recusa versão que não está na lista.
- Data do `GameGuard\GameGuard.ver` de cada cliente: **[O]**
  - v495: 11/07/2007.
  - v548: 11/08/2009.
  - v584: 11/12/2009.
- ~~**[I]** Pela data, as `ggauth` de 2008 devem casar com o GameGuard do v495. O v548 e o v584 podem ser recusados.~~
  Corrigido pela resposta abaixo: o v584 fala o protocolo da `ggauth50`.

### Resposta recebida (outra IA, 20/10/2026)

Relatório: `../../gg-server-emu/RELATORIO-GAMEGUARD-2026-10-20.md`. Os testes foram emulação Unicorn de trechos do servidor
S2, do GameMon v584 e da `ggauth50`, sem carregar nada no Windows. Este projeto não reproduziu. Resumo, só para o v584:

1. **Esquema:** CSAuth2, 16 bytes. Os 16 bytes do fio são o `GG_AUTH_DATA` transformado (Blowfish + XOR, servidor 2007
   `0x4430C0`/`0x443120`, GameMon `0x48163C`/`0x4815C0`). Codec offline: `../../gg-server-emu/tools/csauth2_codec.py`.
2. **Versão:** o GameMon põe 0x10050 no primeiro DWORD da resposta (protocolo da `ggauth50`). O terceiro DWORD traz a
   versão do GameGuard (`AAAAMMDDRR`); no caso 0 deu 2009010101, de estado capturado, não do `GameGuard.ver`.
3. **Pergunta aceita:** o índice escolhe um de 501 casos (0..500). Só o caso 0 foi testado.
4. **Resposta:** o caso 0 usa estado do GameMon (globais capturadas). A `ggauth50` emulada aceitou a resposta calculada
   (0) e recusou com um byte alterado (12).
5. **Prazos:** sem resposta.
6. **Vetores:** nenhum par real. O GameMon fecha ao ver a porta de depuração do GME (`../../gg-server-emu/BLOQUEIO-ATUAL.md`).

O que falta, antes de qualquer `required`: par real de GameGuard ativo, os casos seguintes ao 0, e um validador por
sessão (o `PrtcCheckAuthAnswer` da `ggauth52` aceita qualquer coisa quando não há pergunta pendente). O v495, o v548 e
o HackShield não foram analisados nessa rodada.

### Segunda resposta (outra IA, 20/10/2026)

O que mudou:
- **Dois pares por IPC original** (callback do GME → componente GG), nos índices 0 e 346. Os dois passaram no
  verificador da `ggauth50` emulado em Unicorn. Com um byte alterado, falharam com 12 e 13.
  - As perguntas entraram pelo wrapper Auth2 do cliente, não pela rede: **não são captura de rede** nem provam login completo.
  - Arquivos: `../../gg-server-emu/csauth2-live-ipc-vectors.json` e `tools/verify_live_vectors.py` (só as fixtures; para um par qualquer, `tools/check_pair_files.py`).
- **A primeira DLL é a 50.** O `csauth2.cfg` lista `50 51 52` e o 2007 carrega a primeira como padrão. A conta anterior
  com a 52 não era a do padrão.
- **Ordem das camadas** (`0x4425D0` / `0x442780`):
  - a pergunta interna é copiada para objeto+0x18 **antes** do transporte;
  - o Encrypt/Decrypt só roda se o 1º DWORD interno ≠ 0;
  - o `CheckAuthAnswer` recebe a pergunta **interna**.

  O contrato do validador no `anticheat.py` (`Query(internal, wire)`) segue isso.
- **A negociação só sobe de versão.** O 1º DWORD da resposta escolhe a DLL; versão menor = erro 0xC.
- **O `UpdateTimer` de 300 s é global**, para todas as DLLs. Não substitui os 200/600 s de cada sessão.
- **O GameMon ainda fecha com código 1 por volta de 45 s**, também sem pergunta nenhuma. A causa não foi achada.
- Não há validador em Python: o verificador dos testes executa x86 em Unicorn. Só os casos 0 e 346 foram testados, de 501.
- O 0x1017 fora do GateWater não foi auditado. A política de repetição continua a do 2007.
- O v495 e o v548 não foram iniciados. Ficam sem perfil `required`.

### Terceira resposta (outra IA, 20/10/2026)

1. **A pergunta do fio é invertível** (`Codec.decode_query`, conferida em 103 entradas). Na `ggauth50`, Encrypt e
   Decrypt são no-op (`0x1000EA90`: `xor eax,eax; ret`), então o transporte desfeito já é a pergunta interna. Isso vale
   só para essa DLL. O servidor continua guardando a pergunta interna e a enviada: a inversa é para diagnóstico e não
   substitui pendência, replay nem negociação.
2. **A pergunta inicial fixa pode ser repetida.** Duas vezes no mesmo cliente, as duas respondidas com a mesma
   resposta, sempre por IPC e não pela rede. Isso serve para o capture, mas **não** para vigiar o cliente: a resposta
   igual pode ser reproduzida por quem a gravou. Depois da negociação, a pergunta tem de vir do gerador real.
3. **Validador pela `ggauth50` em Unicorn** dentro do Python de 64 bits: arquitetura viável, mas só parcialmente
   demonstrada. Exige:
   - `PrtcGetVersion(1)`, que não cria o `SetTimer`, mas inicia o relógio e a semente;
   - `PrtcUpdateTimer` a cada 300 s na mesma fila; ele grava o índice em `0x1001AF04` como WORD;
   - estado do CRT por thread: a semente do `rand` fica no TLS (+0x14), índice TLS em `0x10018508`;
   - um único worker serializado, dono do Unicorn; não chamar o mesmo contexto de corrotinas em paralelo;
   - inicializar uma vez, sem reconstruir a imagem nem trocar a semente a cada pacote;
   - em cada sessão: versão negociada, flags (0 → 3 na pergunta, 1 depois do check aceito), pergunta interna e enviada;
   - `GetAuthQuery` com pergunta pendente devolve 11;
   - API não suportada, acesso não mapeado, exceção ou limite de instruções têm de dar falha, nunca 0.

   Endereços da `ggauth50`: GetVersion `0x1000E850`, UpdateTimer `0x1000E890`, GetAuthQuery `0x1000E8A0`,
   CheckAuthAnswer `0x1000E9C0`.
4. **A saída aos ~45 s continua sem causa conhecida.** Todos os testes usaram as mesmas alterações no cliente, então
   não dá para culpar nem inocentar o GameMon original. Os quatro encaminhamentos nativos devolveram NTSTATUS 0 de
   verdade, e a falha do `NtLoadDriver` tem caminho de continuação.

   Depois que o GameMon sai, o wrapper ainda devolve 1, mas nenhum callback chega. Por isso o retorno do wrapper
   sozinho não confirma resposta.

`required` continua bloqueado até existir esse worker e testes reais pela rede (sessão seguinte, erro e timeout).

O servidor ganhou o `mode: capture` para provar o transporte pela rede. A pergunta é `capture-query-protocol50.bin`
(16 bytes, perfil 50).

### Perguntas originais

Responda, para o v584 (e, se der, para o v495), separando **observado / inferido / desconhecido**, com endereço e sha256 do binário (GME desempacotado, `GameMon.des`, `GameGuard.des`):

1. **Esquema.** Ao receber o 0x1015, o GameMon usa CSAuth2 (`GG_AUTH_DATA` de 16 bytes: u32 index, u32 v1, u32 v2, u32 v3) ou CSAuth3 (pacote de tamanho variável)?
2. **Versão.** Que número de versão do GameGuard o cliente informa, e onde (na resposta 0x1016, num campo do `GG_AUTH_DATA`, no 0x1010)? Ele é 50, 51 ou 52?
3. **Pergunta aceita.** Qual 0x1015 o cliente precisa receber para responder um 0x1016? O GameMon confere a pergunta (faixa do index, tabela interna) ou responde qualquer 16 bytes?
4. **Resposta.** Como o 0x1016 é montado a partir da pergunta? Ele depende só dela, ou também de estado do cliente (hora, hash de módulos, sessão)?
5. **Prazos.** Há timeout interno do GameMon entre pergunta e resposta, ou quando nenhuma pergunta chega?
6. **Vetores.** Se o GameGuard rodar no GGEmu, capture pares reais 0x1015 → 0x1016 (seção "O que capturar" acima). Com um par real dá para conferir offline se as `ggauth` aceitam a resposta.

Com essas respostas o servidor segue por um destes caminhos:
- usar as `ggauth` como caixa-preta, num processo auxiliar de 32 bits (exige autorização do dono do projeto para executar essas DLLs);
- portar o algoritmo, se ele for simples;
- manter `observe` e deixar `required` indisponível para a versão que não casar.

## HackShield (TH v404 e S1 v440): o que o servidor sabe e o que falta

O v495 e o S2 (v548/v584) usam GameGuard (seções acima). O TH v404 e o S1 v440 usam HackShield da AhnLab (`EHSvc.dll`). Os clientes do projeto rodam com o patch NoHS.

**Nenhum servidor original do projeto fala HackShield.** Os servidores 2006 e 2007 não têm 0x1018, 0x1019, 0x101B nem 0x101C no dispatcher. Por isso, tudo do lado do servidor abaixo vem só dos clientes. **[O]** = observado no binário, **[I]** = inferido, **[?]** = desconhecido.

### O que o cliente faz

| Cliente | Pergunta S→C | Resposta C→S | Observações |
|---|---|---|---|
| TH v404 (HackShield 3.3) | 0x1018, 48 bytes | 0x1019, 24 bytes em claro | handler `0x521810`. A resposta é calculada sobre o **próprio arquivo GME** na faixa pedida e sai mesmo com NoHS (hash do GME patchado). **[O]** |
| S1 v440 (EHSvc 4.0.0.1) | 0x1018, 160 bytes → ordinal 12 do EHSvc | 0x1019, 56 bytes em claro | **[O]** |
| S1 v440 | 0x101B, 20 bytes → ordinal 13 | 0x101C, 20 bytes em claro | **[O]** |
| S1 v440, em falha | — | mesmo opcode com u32 de erro **cifrado** (16 bytes no fio) | com a DLL ausente responde erro 3 **[O]** |

- **[I]** Pelo tamanho, os ordinais 12/13 parecem `_AhnHS_MakeAckMsg` / `_AhnHS_MakeGuidAckMsg`.
- **[?]** Qual opcode o cliente espera como resultado (0x1017? 0x101A?), os prazos e o que acontece sem pergunta nenhuma.

### O que o servidor faz hoje

- `anticheat: {provider: hackshield, mode: observe}` só registra os 0x1019/0x101C que chegarem: tamanho, sha256[:8] e tempo. Ele não manda 0x1018/0x101B (não tem como gerar a pergunta) e não manda resultado.
- `mode: required` não sobe: não existe validador HackShield e o servidor não aceita sucesso fixo.
- O lado servidor do HackShield é uma lib da AhnLab (`AntiCpXSvr` / HSB: criar o objeto servidor, gerar a pergunta, analisar a resposta). Não temos essa lib nem o arquivo `.hsb` que ela usa.

### Perguntas para quem analisa o cliente (TH v404 e v440)

Separe **observado / inferido / desconhecido**, com endereço e sha256 do GME desempacotado e do `EHSvc.dll`:

1. **Formato da pergunta.**
   - TH: o que são os 48 bytes do 0x1018 (offset e tamanho da faixa do GME, semente, versão)?
   - v440: o que são os 160 bytes do 0x1018 e os 20 do 0x101B? Algum campo é conferido pelo cliente antes de responder (versão, CRC, assinatura)?
2. **Formato da resposta.** Como o 0x1019 (24 bytes no TH, 56 no v440) e o 0x101C (20 bytes) são montados a partir da pergunta? No TH, qual hash (MD5, CRC, próprio) e sobre quais bytes?
3. **Resultado.** O cliente espera um pacote de resultado depois da resposta? Qual opcode e layout? O que acontece com RTC 0 e com RTC ≠ 0 (desconecta, mostra erro, segue)?
4. **Prazos.** O cliente reage a demora ou à falta de pergunta? O EHSvc tem timer próprio?
5. **TH sem DLL.** Se a resposta do TH sai do próprio GME, um servidor que tenha uma cópia do GME **original** (sem NoHS) consegue calcular a resposta esperada? Diga a faixa e o algoritmo para conferirmos offline.
6. **Vetores.** Se der para rodar o HackShield ligado, capture pares reais pergunta → resposta (0x1018 → 0x1019 e 0x101B → 0x101C) com a versão do `EHSvc.dll` e a data.

Com essas respostas o servidor segue por um destes caminhos:
- **TH:** se a resposta for só um hash do GME original, dá para validar no servidor sem a lib da AhnLab;
- **v440:** sem a lib servidor da AhnLab, só `observe`, a menos que o algoritmo seja simples o bastante para portar;
- em qualquer caso, nada de sucesso fixo.
