# GBWC EmuServer

Emulador em Python (asyncio) dos servidores do GunBound: **Broker** (lista de servidores), **Game Server** e um
**Buddy** (amigos). Um mesmo código atende o GunBound Thor's Hammer (TH), World Champion Season 1 (WC S1) e
World Champion Season 2 (WC S2), escolhendo a fase por game server.

Para editar os arquivos do cliente (`.xfs`, `.dat`) há o gbedit, um projeto separado; o `tools/xfs_sync` usa os
leitores dele (veja a variável `GBEDIT_PATH` em [Comandos](#comandos)).

Este README traz o que é comum às três versões. O que muda em cada uma (layouts, opcodes próprios, configuração e
comandos do cliente) está em:

- [README-TH.md](README-TH.md): Thor's Hammer v404
- [README-WCS1.md](README-WCS1.md): World Champion S1 (v440, v495)
- [README-WCS2.md](README-WCS2.md): World Champion S2 (v548, v584)

## Clientes compatíveis (testados)

| Cliente | Fase no `config.yml` | Observação |
|---|---|---|
| TH v404 | `TH` | |
| WC S1 v440 | `WCS1` | sem Grand Prix |
| WC S1 v495 | `WCS1` | sem Grand Prix |
| WC S2 v548 | `WCS2` | com Grand Prix |
| WC S2 v584 | `WCS2` | com Grand Prix, tutorial, jackpot, encantamento |

Todos foram testados sem GameGuard. Como preparar o cliente (GameGuard, registro, `GunBound.gme`) não é coberto
aqui: há muitos tutoriais disso na internet. Este repositório **não** distribui senhas de arquivos `.xfs`/SolFS.

## Requisitos

- Python 3.11+ (testado no 3.11 e 3.13)
- Banco: SQLite (padrão, sem instalar nada), MySQL ou PostgreSQL

## Instalação

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python init_db.py
```

O `init_db.py` cria só as tabelas que faltam e importa os dados iniciais (itens, loja e contas de teste) só em
tabelas novas. Em tabelas que já existem, acrescenta as colunas e os índices (`INDEX`/`UNIQUE`) que faltam: rode de
novo depois de atualizar o servidor. Um `UNIQUE` com dados repetidos não é criado e o script avisa qual. Para outro banco, troque `database.uri` no `config.yml` antes:

| Banco | URI |
|---|---|
| SQLite | `sqlite+aiosqlite:///gbwc.db` |
| MySQL | `mysql+asyncmy://usuario:senha@127.0.0.1:3306/gbwc` |
| PostgreSQL | `postgresql+asyncpg://usuario:senha@127.0.0.1:5432/gbwc` |

Validar a conexão: `python -m tests.smoke_db <uri>`.

Contas de teste do banco inicial: `test` / `test` (jogador) e `Mario` / `mario` (GM, `Authority` 100). Troque as
senhas antes de abrir o servidor para outras pessoas.

## Estrutura do repositório

| Pasta / arquivo | Conteúdo |
|---|---|
| `broker.py`, `game.py`, `buddy.py` | pontos de entrada dos três servidores |
| `init_db.py` | cria/atualiza o banco a partir de `db/` |
| `config.yml` | configuração de broker, game servers, Buddy e banco |
| `gunbound/` | código: `broker/`, `game/` (protocolo por fase em `game/phase.py`), `buddy/`, `repository/` (SQL) |
| `db/linked.sql` | esquema das tabelas (estrutura do servidor original + colunas novas) |
| `db/gbwc.sql` | dados iniciais: itens, loja (`Menu`), níveis de encantamento e contas de teste |
| `data/` | dados de jogo lidos pelo servidor (posições iniciais por mapa) |
| `docs/` | protocolo, layouts de pacotes e análises dos clientes |
| `tests/` | testes unitários (`unittest`) |
| `tools/` | utilitários de linha de comando (veja [Comandos](#comandos)) |

## Configuração (`config.yml`)

- `broker`: host/porta do broker (padrão `8372`, a porta que o cliente procura).
- `gameservers`: lista de game servers. Cada item vira uma linha na lista de servidores do cliente.
  - `name`, `description`, `announcement`: textos mostrados no cliente.
  - `host`, `port`: endereço que o broker anuncia ao cliente. Para jogar pela rede use o IP real, não `127.0.0.1`.
  - `accept`: IPs/faixas CIDR que podem entrar.
  - `phase`: **a fase do cliente que esse servidor atende** (veja abaixo).
  - `version_min` / `version_max`: faixa de versão aceita no login.
  - `gold_factor`, `score_factor`, `grade_min`, `grade_max`, `users_max`, `features` (efeitos e avatar).
  - chaves de cada versão (Grand Prix, jackpot, tutorial...): veja o README da versão.
- `buddy_server`: porta do Buddy (`8352`, TCP e UDP) e `notice` opcional (aviso depois do login). Nos clientes, `BuddyIP`/`BuddyPort` no `GunBound.ini`.
- `broker.th_port` (opcional): porta extra do broker só para o TH, que lê a lista de servidores com outro layout.

### Fase por servidor: TH, S1 e S2

Cada game server atende uma fase. A fase troca os opcodes e os layouts dos pacotes
(`gunbound/game/phase.py`) e também aceita o ProductVersion de login daquela fase.

```yaml
gameservers:
  - name: "GunBound TH"
    port: 8360
    phase: "TH"     # cliente TH v404
    ...
  - name: "GunBound WC S1"
    port: 8361
    phase: "WCS1"   # clientes v440 e v495
    ...
  - name: "GunBound WC S2"
    port: 8362
    phase: "WCS2"   # clientes v548 e v584
    jackpot: *JACKPOT
    tutorial: *TUTORIAL
    grandprix:
      enabled: true
    ...
```

Para atender mais de uma fase ao mesmo tempo, rode um game server por fase, cada um com sua porta.
O `config.yml` do repositório traz dois servidores de exemplo (índice 0 e 1, o 1 com Grand Prix).

## Rodando

| Comando | O que sobe |
|---|---|
| `python broker.py` | Broker |
| `python game.py` | Game server índice 0 de `gameservers` |
| `python game.py 1` | Game server índice 1 (no exemplo, o do Grand Prix) |
| `python buddy.py` | Buddy |

No Windows, sem ativar o ambiente: `.venv/Scripts/python.exe -u broker.py` (idem para os outros).

`game.py [arquivo.yml] [índice]`: o índice escolhe o servidor da lista `gameservers` (cada um num processo, com log
próprio em `logs/`). Suba primeiro o broker e depois os game servers.

Testes: `python -m unittest discover -s tests -p "test_*.py"`.

## Comandos

### Linha de comando (na raiz do repositório, com o `.venv` ativo)

| Comando | O que faz |
|---|---|
| `python broker.py` | Sobe o broker (`broker` do config). |
| `python game.py [arquivo.yml] [índice]` | Sobe um game server; `índice` escolhe o item de `gameservers` (padrão 0). |
| `python buddy.py` | Sobe o Buddy (amigos), TCP e UDP. |
| `python init_db.py` | Cria as tabelas que faltam e importa os dados iniciais. |
| `python -m tests.smoke_db <uri>` | Testa a conexão com um banco. |
| `python tools/fake_launcher.py [usuario] [--host] [--port] [--password]` | Imita o NyxLauncher no broker (0x1310 → 0x3000 → 0x4000). Sem `--password`, pede a senha no terminal. |
| `python tools/give_jackpot_cards.py <usuario> [qtd]` | Dá cartas do Jack Pot Booster Card (S2). O jogador precisa relogar. |
| `python tools/udp_admin.py logout\|gift\|cash <user_no> [host] [porta]` | Manda o UDP administrativo ao game server: `logout` derruba o usuário, `gift` avisa que chegou presente (0x1050), `cash` relê o cash do banco e reenvia (0x6101). |
| `python -I tools/xfs_sync/item_sync.py [--xfs] [--db] [--apply] [--update-prices]` | Sincroniza os itens do `avatar.xfs` com a tabela `Menu`. Sem `--apply` só mostra o plano. |
| `python -I tools/xfs_sync/set_sync.py [--xfs] [--db] [--apply]` | Importa sets e pacotes da loja (`ex1.dat`/`ex2.dat`) para `Menu`. Faz backup do banco antes de gravar. |

O `GunBound.xfs` do S2 é um SolFS cifrado: o `xfs_sync` lê a senha da variável de ambiente `GB_SOLFS_PASSWORD`,
que não é distribuída aqui. Para o TH e o S2 o `xfs_sync` usa os leitores do gbedit: aponte `GBEDIT_PATH` para a
pasta que contém o pacote `gbedit`.

### Comandos de GM no chat (autoridade ≥ 99, `User.Authority`)

Digitados no chat do jogo; a resposta volta como mensagem de admin.

| Comando | O que faz |
|---|---|
| `/server` | Conexões, usuários, salas, usuários em sala e em canal. |
| `/bcm [-a\|-c\|-r] msg` | Mensagem para todos (padrão), só o seu canal ou só a sua sala. |
| `/ban -e\|-dN\|-hN usuario` | Bane para sempre, por N dias ou por N horas e derruba a sessão. |
| `/disconnect nick` | Derruba o jogador. |
| `/close nº` | Fecha a sala e expulsa todos. |
| `/motd -c msg` / `/motd -r msg` | Troca a mensagem do canal ou da sala (até reiniciar). |
| `/room nº` | Mostra modo, vagas, estado e jogadores da sala. |
| `/version`, `/limit`, `/time` | Faixa de versão aceita, faixa de grade, hora do servidor. |
| `/qsman N` | Mínimo de jogadores da entrada rápida (1–8). |
| `/qsopt 1\|2\|3\|4` | Modo da entrada rápida: Solo, Tag, Score, Jewel. |
| `/toid nick` | Mostra o ID de login de um nick. |
| `/silence nick segundos` | Extra deste servidor: proíbe o chat do jogador (0x1040; `0` tira). O bloqueio é feito pelo cliente. No S1 `/mute` também serve. |
| `/startgame` | Extra deste servidor: o GM mestre inicia a partida sem as regras de prontos e times. |

### Comandos que o próprio cliente trata

Nenhum cliente confere autoridade: o que ele não reconhece vai cru para o servidor (0x5100), que só aceita os comandos
de GM acima. Os comandos que cada cliente resolve sozinho (ou transforma em outros pacotes) estão no README da
versão: [TH](README-TH.md#comandos), [S1](README-WCS1.md#comandos), [S2](README-WCS2.md#comandos).

Comandos ocultos em coreano romanizado (iniciar, trocar tanque, espectador, quiz, cores) também existem; os que
depois mandam o texto cru (`/gg`, `/goto`, cores...) não recebem "Syntax Error" do servidor.

### Console de administração (0x5110–0x512C)

Usado pelo console de admin do cliente (login 0x1011). `STATUS`, `MOTD`, `BCM` e o monitor de canal (0x2020) pedem
autoridade ≥ 98; os demais (`SETVERSION`, `GRADELIMIT`, `GUILDLIMIT`, `FUNCTIONRESTRICT`, `SETALLOWEDGUILD`,
`SETEVENTACTPROB`, `SETPASSABLEAUTH`, `SETFACTOR`) pedem ≥ 99. As mudanças ficam em memória até reiniciar.

## Status por opcode

Legenda: ✅ completo · 🟡 parcial / com atalho · ⛔ responde recusando · — não se aplica ou sem gatilho (motivo na nota).
Fases: T = TH, 1 = WC S1, 2 = WC S2.

### Broker

| Opcode | Fases | Status | Notas |
|---|---|---|---|
| 0x1100 lista ordenada de servidores | T12 | ✅ | |
| 0x1310 login | T12 | ✅ | |
| 0x3000 mensagem, 0x4000 iniciar jogo | T12 | ✅ | usados pelo NyxLauncher |
| 0x1311, 0x1320, 0x2000 | | — | nenhum cliente manda ao broker (login de GM, login alternativo, set version) |

### Login e sessão

| Opcode | Fases | Status | Notas |
|---|---|---|---|
| 0x0000 keep-alive, 0x1000 sessão | T12 | ✅ | |
| 0x1010 / 0x1011 login | T12 | 🟡 | teste de versão invertido no caminho de senha pura (v440) |
| 0x1020 user id, 0x1021 nick | T12 | ✅ | |
| 0x1004, 0x1019, 0x101C | T12 | 🟡 | só silenciados, sem resposta |
| S→C 0x101F endereço UDP observado | T12 | ✅ | no UDP de 4 bytes com o token do 0x1012, só se o IP/porta diferir do 0x1010 (NAT) |
| S→C 0x1050 presente chegou | T12 | ✅ | pelo UDP admin 0xF020 |
| S→C 0x1040 mordaça no chat | T12 | ✅ | pelo `/silence` de GM (o original não tem gatilho) |
| S→C 0x1030 billing, 0x1060 e-mail, 0x1111, 0x1113, 0x9001 | | — | o servidor original nunca envia; sem gatilho real, não são enviados |

### Canal e lobby

| Opcode | Fases | Status | Notas |
|---|---|---|---|
| 0x2000 entrar no canal, 0x2010 chat | T12 | ✅ | chat: 2 bytes desconhecidos fixos em 0 |
| 0x2020 / 0x2022 monitor de canal (admin) | T12 | ✅ | |
| 0x2100 / 0x2101 lista de salas | T12 | 🟡 | lista enviada a todo o lobby |

### Salas

| Opcode | Fases | Status | Notas |
|---|---|---|---|
| 0x2104 detalhe, 0x2110 entrar, 0x2120 criar | T12 | ✅ | 0x2105: u32 extra fixo em 0 |
| 0x3100–0x3104 mapa, opção, itens, vagas, título | T12 | ✅ | |
| 0x3150 expulsar, 0x3200 mobile, 0x3210 time, 0x3230 pronto | T12 | ✅ | |

### Partida

| Opcode | Fases | Status | Notas |
|---|---|---|---|
| 0x3430 iniciar, 0x3232 voltar à sala | T12 | 🟡 | posição inicial sempre do lado A; vidas (Score) sem fonte |
| 0x4100 morte, 0x4104 ressurreição, 0x4200 fim jewel, 0x4500 túnel | T12 | ✅ | |
| 0x4412 resultado | T12 | 🟡 | limites de gold/GP por partida próprios |
| 0x4000 queda de jogador | T12 | ✅ | o v584 não envia |

### Loja, baú e presentes

| Opcode | Fases | Status | Notas |
|---|---|---|---|
| 0x6000 baú | T12 | 🟡 | cauda u32 do baú fixa em 0; extras do avatar (10 bytes) em 0 |
| 0x6020 comprar, 0x6024 consumir, 0x600E salvar avatar | T12 | ✅ | |
| 0x6028 presente (antigo), 0x600A local do item | T12 | ✅ | o v584 não envia |
| 0x6100 cash, 0x6104 gold | T12 | ✅ | |

### Opcodes de cada versão

Grand Prix, presentes do WC, entrada rápida e os recursos do S2 (tutorial, jackpot, encantamento, caça-níquel, loja
nova...) estão nos READMEs por versão: [TH](README-TH.md), [S1](README-WCS1.md), [S2](README-WCS2.md).

### GM e console de administração

| Opcode | Status | Notas |
|---|---|---|
| 0x5010 BCM, 0x5100 comandos GM | 🟡 | comandos dos modos 3 e 4 incompletos |
| 0x5110–0x512C console (status, MOTD, versão, limites, fatores...) | ✅ | |
| 0x5000 denúncia | ✅ | o v584 não envia |

### Buddy (amigos)

✅ BuddyServ próprio (`buddy.py`, porta 8352 TCP e UDP): login cifrado, lista com grupos, adicionar/remover/agrupar,
busca, estado online, túnel de mensagens e mensagens guardadas para quem está offline. O pedido de amizade é P2P pelo
túnel. O WC S2 v584 também (layout próprio, login validado pela sessão do game; sem busca). Protocolo em
[docs/BuddyServ.md](docs/BuddyServ.md).
O cliente só conecta se o `GunBound.ini` tiver `BuddyIP` (e `BuddyPort`, padrão 8352).

### Testes

`python -m unittest discover -s tests -p "test_*.py"` (todos passam).

## Licença

[GNU Affero General Public License v3.0](LICENSE). Se você rodar uma versão modificada deste servidor para outras
pessoas pela rede, precisa disponibilizar o código-fonte dela.

GunBound é marca de seus respectivos donos. Este projeto não é afiliado a eles e não distribui o cliente.
