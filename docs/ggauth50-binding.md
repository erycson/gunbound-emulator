# Binding experimental ggauth50: Python x64 → helper Windows x86

Implementação em 20/10/2026. **Não qualificada para `required`**. O smoke test
nativo da DLL passou; não foi feito teste conectado ao cliente. A suíte de unidade
usa um worker falso explicitamente separado; sua evidência é distinta da nativa.
Não reiniciamos nem alteramos a configuração do servidor em execução.

## Entrega e integração

- `gunbound/game/ggauth50.py`: subprocesso privado e adaptador asyncio por sessão.
- `ggauth50_helper.py`: ABI cdecl com ctypes.CDLL, chamadas nativas em uma única
  thread x86, inclusive `PrtcGetVersion(1)` e `PrtcUpdateTimer()` a cada 300 s.
- `ggauth50_codec.py`: transporte S2 em Python; constantes e chave lidas do PE
  original após conferir SHA-256. Nenhuma chave está gravada no código.
- `tests/test_ggauth50.py`: ABI, estado, limites, IPC, timeout/crash/reinício,
  cancelamento, concorrência, replay e integração observe.

A base anticheat foi commitada por outra IA durante este trabalho. Este commit
inclui somente os ajustes próprios de integração em anticheat e GameServer,
além dos arquivos novos listados acima. Não inclui outras alterações anteriores.

Os ajustes permitem métodos assíncronos query/check, registram o adaptador por
configuração, cancelam suas tarefas no fechamento e fecham o helper no stop do
GameServer. Não registram o binding como validador confirmado em `VALIDATORS`.
Observe conserva o contrato anterior: emite 0x1017 RTC 0 somente após check
verdadeiro de uma pergunta pendente; sem validador ou em falha nunca emite.
Required continua bloqueado; off/capture com este binding são recusados.

## Preparação pelo operador

1. Disponibilize um Python **Windows x86** (32 bits), sem necessidade de pip ou
   pacotes adicionais para o helper. O servidor pode continuar Python x64.
2. Copie os arquivos próprios para `vendor/gameguard/`, conforme o README daquela
   pasta. DLLs, executáveis originais e CRTs não são distribuídos nem commitados.
   Dependências só podem ser resolvidas na pasta aprovada da DLL ou System32.
3. Escolha explicitamente a versão mínima no formato YYYYMMDDRR. A versão mínima
   do servidor original ainda não foi estabelecida: não há default disfarçado de
   configuração fiel ao S2. O exemplo abaixo serve apenas ao v584 observado.
4. Em uma configuração de teste, após revisão, use:

```yaml
anticheat:
  provider: gameguard
  mode: observe
  validator: ggauth50
  requery: 200
  deadline: 600
  ggauth50:
    python_x86: 'C:\Python32\python.exe'
    dll: 'D:\GBWCProject\server\vendor\gameguard\ggauth50.dll'
    original_server: 'D:\GBWCProject\server\vendor\gameguard\GunBoundServ3.exe'
    minimum_version: 2009010101
    timeout: 5
```

Não houve alteração no config.yml em uso. Não é necessário mudar o registro,
HTTP, hosts ou os arquivos do cliente para preparar o binding.

## Contrato, estado e falhas

IPC sem porta TCP: pipes herdados stdin/stdout, JSON UTF-8 com prefixo uint32
little-endian e limite 4096 bytes. Diagnósticos não recebem corpos de auth.
O handshake exige contrato 1, protocolo 0x10050, x86 e hash exato da DLL.
Fila do parent limitada a 64; prazo inclui espera na fila. O reader do helper
tem fila 8. Cada helper aceita até 1024 sessões.

O helper atribui IDs aleatórios opacos e guarda Version (12 bytes), flags,
pergunta interna, resposta anterior e contador monotônico por sessão. Query
dupla e check sem pendência são recusados antes de qualquer chamada nativa.
Uma resposta inválida consome a pendência e invalida a sessão no helper. O
adaptador não restaura flags nem transforma retorno zero isolado em sucesso.
Versão inicial vem do DWORD 2 da resposta e passa por limites de data, mínimo
configurado e protocolo 0x10050; não há negociação improvisada com 51/52.

O descriptor_flags é 0 neste escopo experimental. Os transforms da DLL50 exata
são no-op confirmados; outras DLLs e versões são recusadas pelo hash. O índice
temporal, CRT rand e TLS são mantidos pelo loader/CRT reais da única thread.
Não há reseed por pacote. Timer global de 300 s separado dos 200/600 s por sessão.

Morte, timeout, protocolo malformado ou generation divergente encerram o helper
e invalidam todas as sessões associadas. A mesma sessão nunca reanexa a um
processo novo. Não há retry que conserve autenticação. Um novo conjunto de
sessões pode criar outro helper, perdendo o estado anterior. Observe só registra
a falha sem derrubar o jogador; sucesso exige check real positivo. O stop do GameServer fecha seu
helper; fechar uma sessão libera apenas seu estado, sem interromper outras.

## Testes e limite de evidência

```powershell
.venv/Scripts/python.exe -m unittest tests.test_ggauth50 tests.test_anticheat
```

O teste do timer usa um intervalo reduzido e verifica identidade da thread;
não é um teste nativo de 300 segundos. Fixtures falsas nunca são selecionáveis
pela configuração de produção. Testes do codec podem ler o PE original, mas
não o executam. Não há DLL binária em fixture.

Resultado da suíte direcionada: **34 testes passaram** (binding/IPC e regressão
anticheat), incluindo falha de hash antes de iniciar qualquer worker.

Antes de liberar required: revisar política de versão mínima e descriptor_flags,
testar com o cliente/servidor em instância isolada e exercitar o ciclo periódico
com respostas geradas por um cliente real. Não afirmar cobertura dos 501 casos
com somente dois pares. A estabilidade do GameMon continua independente.

## Evidência nativa em 20/10/2026

Foi usado CPython 3.13.0 embeddable **win32**, baixado da distribuição oficial
`https://www.python.org/ftp/python/3.13.0/python-3.13.0-embed-win32.zip`, sem instalar
ou configurar o sistema. SHA-256 medido do ZIP:
`bc57b9c6b570ff667fbd7165a4068f3f7757935808c8fa1bd94b64bacdb9d90d`.
`python.exe` e `python313.dll` tiveram Authenticode **Valid**, assinante Python
Software Foundation; o interpretador confirmou ponteiros de 32 bits.
Runtime temporário e binários proprietários não entram no commit.

`tools/qualify_ggauth50.py` foi executado pelo Python x64, que abriu o helper x86
real por pipes: duas sessões intercaladas produziram a pergunta inicial esperada
e aceitaram a resposta IPC real, replay foi recusado no adaptador, a pergunta
seguinte foi gerada pela DLL, e mutação do último byte do corpo no fio foi
recusada. Os processos foram encerrados no finally, sem tocar no servidor em uso.

`tools/check_ggauth50_native_vectors.py`, executado diretamente no Python x86,
inicializou uma Session **diagnóstica** com versão 2009010101, flags 3 e a pergunta
interna salva, sem expor injeção de estado no IPC de produção:

| Caso | Original | Último byte interno alterado | Último byte no fio alterado |
|---|---:|---:|---:|
| Inicial | 0 | 14 | 12 |
| Índice 346 | 0 | 0 | 13 |

Assim, não é correto afirmar que toda alteração de qualquer byte interno é
recusada: a alteração interna específica acima continua aceita no caso 346.
As mutações no fio reproduzem os retornos 12/13 da referência offline.
`PrtcUpdateTimer()` foi também chamado de verdade e retornou 0 na mesma thread.

Comandos, sem exigir DLLs no Git:

```powershell
python tools/qualify_ggauth50.py --python-x86 <python32.exe> --dll <ggauth50.dll> --original-server <GunBoundServ3.exe> --wait-timer
<python32.exe> -I tools/check_ggauth50_native_vectors.py --dll <ggauth50.dll> --original-server <GunBoundServ3.exe>
```

O primeiro comando com `--wait-timer` mantém o helper por 301 s e só registra
sucesso do timer se o contador confirmar uma chamada nativa concluída de verdade.
O segundo fixa estado apenas para comparar fixtures; não é o fluxo de uma sessão
nova, nem um gerador de respostas. Ambos verificam o SHA-256 exato antes do load.

O teste nativo de **301 segundos foi concluído com exit code 0**: o handshake
confirmou `native_300_second_timer_observed=true`. A revisão final repetiu os
34 testes de unidade/integração, todos aprovados, e os dois vetores nativos.
Resultados resumidos em `ggauth50-native-qualification.json`. Isso confirma o
timer real desta execução; não substitui o teste periódico conectado ao cliente.
