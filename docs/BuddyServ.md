# BuddyServ (amigos)

Implementação: `gunbound/buddy/server.py`, `gunbound/repository/buddy_repository.py`, `buddy.py`. Testes: `tests/test_buddy.py`.
Fontes (só análise estática): cliente TH v404 (`CBuddy2`, OnMsg `0x4e8c00`, SendServ `0x4e9b90`, P2P `0x4ec060`) e
`server-original/BuddyServ/BuddyServ2.exe` (dispatch `0x40e360`, login `0x40f090`, lista `0x406d04`).
O BuddyCenter (8382) não é necessário: com um BuddyServ só, a presença fica num mapa em memória `Id -> sessão`.

## Conexão

- O cliente conecta logo depois de entrar no game server (`0x44c6ca`), em `BuddyIP:BuddyPort` do `GunBound.ini`
  (sem `BuddyIP` não conecta; porta padrão 8352).
- TCP e UDP na mesma porta. Framing: `u16 tamanho total | u16 comando | corpo` (sem seq/checksum).
- Respostas começam com `u16 rtc` (0 = OK). Erros do original: 4 BD, 7 tamanho, 9 quantidade, 0x10 não achado,
  0x11 senha/cifra, 0x50 lista cheia (500), 0x51 já está na lista, 0x60 versão.

## Cifra

- Chave estática `2C45926CF3396642B670D006A1FA8182` (cliente `DAT_005516b4`, servidor `0x442f18`): só os 2 primeiros
  blocos do login.
- Chave de sessão = `SHA0(Id + senha + nonce u32 LE)[:16]` (= `CryptoManager.derive_key`).
- Blocos: AES-ECB de `[u32 0x2DBABE65][12 bytes]`. O magic é fixo (no game é `cmd + 0x79CE9F82`).
- Cifrados: C→S 0x1010 (parte), 0x2000, 0x2030; S→C 0x2010.

## Login

1. C→S `0x1000` vazio → S→C `0x1001` `u32 nonce`.
2. C→S `0x1010` (0x50 bytes): `AES_static(Id[16])`, `AES_static(nonce + lixo)` (o original ignora),
   48 bytes cifrados com a chave de sessão: `u32 versão (0x19)`, `senha[20]`, `u32 IP local`, `u16 porta UDP local`, lixo.
   A senha é a pura ou, via NyxLauncher, md5 hex `[12:32]` (as duas são aceitas, como no game).
3. S→C `0x1011`: `rtc, u32 token, nick[12], guild[8], u16 grade, u16 n` + n × `Id[16], nick[12], categoria, guild[8], u16 grade`.
   Categoria: `str[20]` quando muda em relação à anterior (lista ordenada por Category); senão 1 byte 0.
4. Depois: `0x3FFF` com o estado dos amigos, `0x2010` com as mensagens guardadas (até 15 por pacote),
   `0x1FFE` aviso (opcional, `buddy_server.notice`), e `0x3FFF` de 1 entrada para quem tem o usuário na lista.
5. O cliente manda o token por UDP; o servidor ecoa, guarda o endereço público e, se for diferente do declarado,
   manda `0x101F` (`u32 ip, u16 porta`) e reavisa os amigos.
6. Login duplicado: a sessão antiga recebe `0x1FFF` (`u16 0`) e é fechada.

## Comandos

| C→S | Corpo | Resposta |
|---|---|---|
| 0x0000 | — | keep-alive, nada |
| 0x3000 ADD | `Id[16], categoria[20]` | 0x3001 `rtc, Id[16], nick[12], guild[8], u16 grade` + 0x3FFF do amigo. Unilateral: o pedido/aceite é P2P |
| 0x3002 REMOVE | `Id[16]` | 0x3003 `rtc, Id[16]` |
| 0x3004 GROUP | `u16 n, n×Id[16], categoria[20]` | 0x3005 `rtc` |
| 0x3006 RENAME | `antiga[20], nova[20]` | 0x3007 `rtc` |
| 0x3010 STATE | `Id[16]` | 0x3FFF de 1 entrada |
| 0x4000 SEARCH | `nick[12], Id[8] (prefixos), u16 offset, u16 count` | 0x4001 `rtc, u16 n, n×(Id[16], nick[12], guild[8], u16 grade)` |
| 0x2020 TUNNEL | `u8 guardar, u16 código, u16 tam, dados, u16 n, n×Id[16]` | cada destino online recebe 0x2021 `Id_de[16], nick_de[12], u16 código, u16 tam, dados`; offline com `guardar` vai para `packet` |
| 0x2000 SAVE (cifrado) | `Id_destino[16], u16 código, u16 tam, dados` | entrega 0x2021 se online, senão guarda em `packet` |
| 0x2011 ACK | `u16 n, n×u32 SerialNo` | apaga de `packet` |
| 0x2030 SMS (cifrado) | `Id[16], u16 tam, texto` | 0x2031 `rtc`; entrega como código P2P 0xC013 |

`0x3FFF`: `u16 n` + n × `Id[16], u8 online` [+ `u32 ip público, u16 porta, u32 ip local, u16 porta` se online],
IP/porta em ordem de rede.

`0x2010` (cifrado): `u16 n` + n × `u32 SerialNo, Id_de[16], nick_de[12], u32 unix_time, u16 código, u16 tam, dados`.

## Códigos P2P (dentro do túnel, o servidor só repassa)

c011 chat, c013 SMS, c018 mensagem de presente, c041 pedido de amizade, c042 resposta (`u8 aceito` + texto),
c043 remoção, c051/c053 estado, c01a–c01d foto. Fluxo do ADD: A manda c041 → B aceita: c042(1) para A e 0x3000(A) →
A recebe c042(1) e manda 0x3000(B). Os dois lados gravam pelo próprio 0x3000; o servidor não grava nada sozinho. Diferença do original: 0x3000 de quem já está na lista responde OK com os dados (o original manda 0x51, que o cliente ignora e o amigo some da tela).

## Comportamento do cliente (TH)

- **GM não vê amigo novo na hora:** com TotalGrade 20 (GM), os sinks do cliente saem sem fazer nada no 0x3001
  (`0x4046e0`: `cmp word [game+0x3ad66],0x19`), no c041/c042 e no chat c011. O amigo só aparece no próximo login
  (o sink do 0x1011, `0x403d30`, não tem o bloqueio). O servidor responde certo; para testar use contas sem GM.
- **Amigo na lista de servidores:** não passa pelo servidor além do repasse.
  - Ao entrar num canal (0x2001 RTC 0), o cliente guarda o **u16 índice** da linha escolhida no 0x1102
    (TH `0x44c68f`, v440 `0x4f280b`, v584 `0x515008`) e manda o P2P **c051** aos amigos (TH `0x404cb0`/`0x404a00`).
  - c051: `u16 0x12`, 6 bytes, `u16 servidor` (+8, o índice acima; 0xFFFF fora de servidor), `u16 canal` (+0xA),
    `u16 sala` (+0xC), `u16 checksum` (+0xE) = soma de `b[8+i] ^ "comsik"[i]`, 8 bytes. Também sai ao ver o amigo online,
    ao adicionar, ao aceitar e ao receber c053. O túnel 0x2020→0x2021 repassa sem mexer.
  - Quem recebe grava em `nó+0x31` (v584 `+0x3d`) e a tela de servidores conta, a cada quadro, os amigos com
    estado 0x12 e `servidor == índice da linha` (TH `0x402350`, v440 `0x403b60`, v495 `0x403c20`, v584 `0x403780`).
  - **Só o WC S1 (v440/v495) desenha:** ícone fixo `serverlist_back.img` (0xde2b0) quadro 5 na linha (v440 `0x51cfa0`,
    v495 `0x52c7c2`). O TH e o v584 calculam a contagem e não a leem; o TH usa os mesmos dados na aba de servidores dos
    amigos (0x1101). As animações por linha do v584 vêm do i8 evento do 0x1102, não de amigos.
  - Por isso o servidor só precisa de: `index` fixo por servidor no 0x1102 (posição em `gameservers`, igual para todos)
    e o repasse do túnel. A conexão com o Buddy só existe depois do 1º canal: a marca aparece ao **voltar** para a
    lista de servidores, não na primeira tela.
  - [INCERTO] O v440 troca o c051 pelo 0xa510 (outra conexão, `0x4080f0`) quando `[0x870564]` não é nulo.
- **v584:** layout próprio, ver a seção abaixo.

## WC S2 v584 (Buddy2.dll, versão 0x1B)

Mesmo framing, cifra, magic e chave estática; os comandos são os mesmos, com outro layout. Lido no `Buddy2.dll` e no
`.gme` do v584. Implementado em `gunbound/buddy/server.py` (`login_v584`, `BuddySession.uid/nick_bytes`).

- **Id de 20 bytes** em todos os pacotes; nick e guild em **UTF-16LE** `wchar[20]` (40 bytes).
- **0x1001 de 8 bytes:** `u32 nonce, u32 recursos` (máscara mínima 0x7601). O TH/S1 exigem exatamente 4 bytes e o v584
  exatamente 8, então o servidor manda os dois 0x1001 e cada cliente descarta o outro.
- **0x1010 de 0xD0 bytes:** AES estático(`Id[0:16]`) + AES estático(`Id[16:20]`, `u32 nonce`, 8 de lixo) + 11 blocos
  com a chave de sessão: `u32 versão 0x1B`, `senha[20]` (sempre vazia), IP `@0x18`, porta UDP `@0x1C`, nick `@0x1E`,
  guild `@0x46`, ext16 `@0x6E`, lixo.
- **Sem senha:** a chave é `derive_key(Id, '', nonce)`. O servidor só aceita quem está no `CurrentUser` (logado num
  game server) e cujo último `LoginLog.Ip` é o mesmo IP da conexão do Buddy; senão responde 0x1011 `0x11`.
- **Login:** 0x1012 (`u16 n` + n × 0x94: Id20, nick w40, guild w40, ext16, ext32[32]; até 175 por pacote) **antes**
  do 0x1011 (`u16 rtc, u32 token`), depois 0x3FFF e 0x2010. Sem amigos, o 0x1012 não vai.
- **ext16:** `u16 grade mostrada, u16 TotalGrade, 12 × 0xFF`. De amigo online no v584 vai o ext16 que ele mandou no
  login; senão o servidor monta com a TotalGrade.
- 0x3FFF: `Id20 + u8 online [+ ip4, porta2, ip4, porta2]` (0x21 ou 0x15 bytes por entrada).
- 0x3000: `Id20 + ext32[32] + u16` → 0x3001 de 0x98 bytes: `rtc` + entrada de 0x94 + `u16` ecoado. Sem grupos.
- 0x3002: `Id20` → 0x3003 `rtc + Id20`. 0x3010: `Id20`.
- 0x2020: `u8 guardar, u16 código, u16 tam, dados, u16 n, n × Id20` → 0x2021: `Id20, nick w40, u16 código, u16 tam, dados`.
- 0x2000/0x2030 cifrados: destino Id20. SMS P2P é **0xC015** (0xC013 no TH).
- 0x2010: `u16 n` + n × (`u32 serial, Id20, nick w40, u32 hora, u16 código, u16 tam, dados`).
- Não existe busca (0x4000/0x4001) no v584; o 0x1FFE (aviso) chega a um sink vazio, então o servidor não manda.
- **TH/S1 × v584 não trocam P2P:** Id e texto têm formatos diferentes. O servidor não repassa 0x2021 entre versões
  diferentes (só registra no log); mensagem guardada para alguém offline de outra versão chega ilegível.
- O `.gme` ignora 0x3001 e c041 quando a própria TotalGrade é 0.

## Pendências

- 0x5000 (broadcast vindo do Center) não é usado: não há Center.
- O P2P por UDP direto entre clientes depende da rede; sem rota, o cliente usa o túnel 0x2020, que funciona sempre.
