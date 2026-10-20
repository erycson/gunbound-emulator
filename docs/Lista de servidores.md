# Lista de servidores (broker)

A lista que o cliente mostra vem do broker, que lê a seção `gameservers:` do `config.yml`.
Cada item da lista é um game server. A posição dele na lista (0, 1, 2, …) é o seu **índice**.

## Exemplo com dois servidores

```yaml
gameservers:
  - name: "Gunbound WC"            # máx. 32 bytes (latin-1)
    description: "Área livre\\nSem avatar"   # máx. 64 bytes; \\n quebra a linha
    announcement: "# Bem vindo"     # mensagem ao entrar no canal
    host: "127.0.0.1"               # IP que o CLIENTE usa para conectar (use o IP público/LAN para jogar fora da máquina)
    port: 8360                      # TCP do jogo + UDP de status (o broker consulta por UDP)
    accept: [127.0.0.1, 64.0/1]     # quem pode entrar (CIDR)
    version_min: 440
    version_max: 440
    product_version: *product_version
    phase: "WCS1"                   # TH, WCS1 (v440, v495) ou WCS2 (v548, v584); padrão WCS1
    users_max: 3000                 # máx. 65535
    event: 0                        # tipo na lista: 0 normal, 1 = fundo wowlg, 2 = Grand Prix (automático com grandprix.enabled)
    grade_min: 19                   # faixa de patente aceita
    grade_max: -4
    gold_factor: 230                # % de ouro (100 = normal)
    score_factor: 270               # % de GP
    stats_interval: 300
    features: [*AVATAR_ENABLED, *EFFECT_FORCE]   # bits da tabela "features" no topo do arquivo

  - name: "Gunbound Avatar Off"
    description: "Sem avatar"
    host: "127.0.0.1"
    port: 8361                      # cada servidor precisa de porta própria
    # ... demais campos iguais ao primeiro (todos obrigatórios, menos phase e as chaves de cada versão)
```

## Subir cada servidor

`game.py` recebe o índice como argumento (padrão 0):

```
python game.py 0   # primeiro da lista
python game.py 1   # segundo
```

Para um segundo servidor, copie `servidor-game.bat` e troque a última linha por `".venv\Scripts\python.exe" -u game.py 1`.
O broker (`servidor-broker.bat`) é um só e lista todos.

O `servidor-game-grandprix.bat` já faz isso para o Grand Prix (ver [Grand Prix.md](Grand%20Prix.md)).
As chaves próprias de cada versão (Grand Prix, jackpot, tutorial...) estão nos READMEs:
[TH](../README-TH.md), [S1](../README-WCS1.md), [S2](../README-WCS2.md).

## Como o broker monta a lista
- A cada ciclo ele manda um UDP `0xF000` para `host:port` de cada servidor; quem responde `0xF001` aparece como
  online, com usuários, patentes e avatar vindos da resposta. Quem não responde aparece offline, e os registros
  dele em `CurrentUser` são apagados na hora.
- Pacote ao cliente: 0x1100 → 0x1102 em `gunbound/broker/protocol/server_sorted_list.py`. O byte de tipo depois do
  índice é o `event` (2 = Grand Prix, ver [Eventos.md](Eventos.md)).
- **TH:** lê o 0x1102 com outro layout (13 bytes depois da descrição: ip, porta, 3 u16, online). O broker só sabe que é
  o TH pela porta: ligue `broker.th_port` (ex.: `8373`) e aponte o `Port=` do `GunBound.ini` do TH para ela. O TH
  também pede **0x1101** (aba dos servidores dos amigos): até 16 índices u16; a resposta é um 0x1102 só com eles.
- O broker também atende o NyxLauncher (0x1310 login, 0x3000, 0x4000); ver `tools/fake_launcher.py`.
- `host` precisa ser alcançável pelo cliente **e** pelo broker. Se o broker e o jogo rodam na mesma máquina mas os
  jogadores vêm de fora, use o IP externo e libere TCP+UDP da porta no firewall.
- Nome/descrição maiores que o limite impedem o broker de iniciar (erro explica qual).
