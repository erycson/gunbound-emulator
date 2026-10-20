"""
Anti-hack: config global `anticheat: {provider, mode}` no topo do config.yml (docs/gameguard-protocol.md); ligar ou
não é decisão de configuração, não da versão do cliente. Um `anticheat` dentro do game server sobrepõe o global.

provider: none | gameguard | hackshield      mode: off | observe | capture | required

- off: não manda desafio nem responde (comportamento de sempre; os clientes do projeto têm patch NoGG/NoHS).
- observe: registra cada resposta que chegar; sem validador nunca responde 0x1017. Com validador manda desafios,
  registra o veredito e só envia 0x1017 após check verdadeiro da pergunta pendente, sem derrubar ninguém.
- capture (só gameguard): manda uma vez o 0x1015 fixo de `capture_query` (16 bytes já no formato do fio) e grava o
  0x1016 em `capture_out` (JSON por linha) para conferir offline. Não valida, nunca manda 0x1017, nunca derruba.
- required: exige um validador confirmado (sobe com erro se não houver); resposta inválida, repetida, fora do
  tamanho ou atrasada derruba a conexão, como o servidor 2007 (0x42b9d0 retorna 0 -> closesocket).

O binding experimental ggauth50 usa um helper Windows x86, somente em observe (docs/ggauth50-binding.md).
Não está registrado como validador confirmado para required. Contrato do validador
(servidor 2007, wrappers 0x4425D0/0x442780):
- pergunta: GetAuthQuery -> cópia interna (objeto+0x18) -> Encrypt só se o 1º DWORD interno != 0 -> 0x4430C0 -> fio;
- resposta: fio -> 0x443120 (XOR diferente do da pergunta) -> Decrypt só se o 1º DWORD interno != 0 -> CheckAuthAnswer
  com a pergunta INTERNA guardada, nunca com a do fio;
- o 1º DWORD da resposta escolhe a DLL (só sobe; versão menor = erro 0xC). O csauth2.cfg do 2007 lista 50 51 52, então a
  primeira pergunta sai da ggauth50; o v584 responde 0x10050;
- o PrtcUpdateTimer roda a cada 300 s para todas as DLLs (estado global), separado dos 200/600 s de cada sessão;
- tem de manter a recusa de resposta sem pergunta pendente: o PrtcCheckAuthAnswer da ggauth52 devolve 0 (ok) nesse caso.
Por isso `VALIDATORS` está vazio e required não sobe. O sucesso (0x1017 RTC 0) só sai depois de Validator.check()
verdadeiro; não há caminho de sucesso fixo.

Logs (prefixo [anticheat]): sessão anônima (contador, sem usuário), provider, modo, passo, opcode, tamanho,
sha256[:8] do corpo, duração em ms e resultado. O corpo só vai para o arquivo do capture, nunca para o log.
"""
from __future__ import annotations
import asyncio
import hashlib
import itertools
import inspect
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Protocol, TYPE_CHECKING
from gunbound.game.protocol.base import Packet
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection

PROVIDERS = ('none', 'gameguard', 'hackshield')
MODES = ('off', 'observe', 'capture', 'required')
CAPTURE_OUT = 'gg-capture.jsonl'
# servidor 2007 (0x412770): nova pergunta 200 s e 300 s depois da última resposta boa; sem resposta boa em 600 s cai
REQUERY_SECONDS, DEADLINE_SECONDS = 200, 600


@dataclass(frozen=True)
class Exchange:
    challenge: int              # S->C
    challenge_len: int
    answer: int                 # C->S
    answer_lens: tuple[int, ...]


# Tamanhos observados nos clientes (RE estática, relatório gg_cli). A falha local do cliente volta no mesmo opcode
# como u32 cifrado (16 bytes no fio): no GameGuard tem o mesmo tamanho do CSAuth2, então só o validador distingue.
PROFILES: dict[str, tuple[Exchange, ...]] = {
    'gameguard': (Exchange(0x1015, 16, 0x1016, (16,)),),                         # CSAuth2 sem a cifra da sessão: v495, v548, v584
    'hackshield': (Exchange(0x1018, 160, 0x1019, (56, 24, 16)),                  # v440 160/56; TH 48/24 (mesmo opcode)
                   Exchange(0x101B, 20, 0x101C, (20, 16))),                      # só v440
}
RESULT_OK = {'gameguard': 0x1017}   # 0x1017 RTC 0 (no v584 dispara o probe UDP e muda a cena); HackShield: sem fonte
ANSWERS = {e.answer: (provider, e) for provider, ex in PROFILES.items() for e in ex}


@dataclass(frozen=True)
class Query:
    internal: bytes     # pergunta antes do transporte (objeto+0x18 no 2007): é ela que vai ao check
    wire: bytes         # corpo do desafio no fio (0x1015)


class Validator(Protocol):
    """Uma instância por sessão: guarda o descritor (DLL) escolhido na negociação, como objeto+0x00 no 2007."""
    def query(self, exchange: Exchange) -> Query | Awaitable[Query]: ...
    def check(self, exchange: Exchange, internal: bytes, answer: bytes) -> bool | Awaitable[bool]: ...   # answer = corpo cru do fio


VALIDATORS: dict[str, type] = {}    # nenhum confirmado; um validador de verdade entra aqui (ex.: ponte para o ggauth)


def capture_query(cfg: dict) -> bytes:
    """Corpo fixo do 0x1015 do modo capture (ex.: gg-server-emu/capture-query-protocol50.bin, perfil ggauth50)."""
    path = cfg.get('capture_query')
    if not path:
        raise ValueError("anticheat: mode capture exige capture_query (arquivo com os 16 bytes do 0x1015)")
    try:
        body = Path(path).read_bytes()
    except OSError as e:
        raise ValueError(f"anticheat: capture_query ilegível: {e}") from e
    if len(body) != PROFILES['gameguard'][0].challenge_len:
        raise ValueError(f"anticheat: capture_query tem {len(body)} bytes, o 0x1015 tem 16")
    return body


def settings(config: dict) -> tuple[str, str]:
    """Lê e valida `anticheat` do gameserver; required sem validador confirmado é erro de configuração."""
    cfg = config.get('anticheat') or {}
    mode = cfg.get('mode', 'off')
    mode = 'off' if mode is False else str(mode).lower()  # YAML 1.1: off sem aspas vira False
    provider = str(cfg.get('provider', 'none')).lower()
    if provider not in PROVIDERS or mode not in MODES:
        raise ValueError(f"anticheat inválido: provider={provider} mode={mode} (provider {PROVIDERS}, mode {MODES})")
    if provider == 'none':
        mode = 'off'
    if cfg.get('validator') in ('ggauth', 'ggauth50'):
        from gunbound.game.ggauth50 import validate_config
        validate_config(cfg)
    elif cfg.get('validator'):
        raise ValueError('anticheat: unknown validator')
    if mode == 'required' and provider not in VALIDATORS:
        raise ValueError(f"anticheat: mode required com provider {provider} exige um validador confirmado, e não há "
                         f"nenhum (docs/gameguard-protocol.md). Use observe ou off.")
    if mode == 'capture':
        if provider != 'gameguard':
            raise ValueError("anticheat: mode capture só existe para gameguard (HackShield não tem pergunta conhecida)")
        capture_query(cfg)
    return provider, mode


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()[:8]


class AntiCheat:
    """Estado anti-hack de uma conexão (separado do login). Timers são cancelados em close()."""
    _ids = itertools.count(1)

    def __init__(self, conn: 'ClientConnection', provider: str = 'none', mode: str = 'off', validator: Validator | None = None,
                 requery: float = REQUERY_SECONDS, deadline: float = DEADLINE_SECONDS,
                 capture: bytes | None = None, capture_out: str = CAPTURE_OUT):
        self.conn, self.provider, self.mode, self.validator = conn, provider, mode, validator
        self.requery, self.deadline = requery, deadline
        self.capture, self.capture_out = capture, capture_out
        self.sid = f"{next(self._ids):05d}"
        self.pending: dict[int, tuple[Query, float]] = {}   # opcode da resposta -> (pergunta, hora)
        self.timers: list[asyncio.TimerHandle] = []
        self.started = 0.0
        self.closed = False
        self.tasks = set()
        self.asking = False

    @classmethod
    def from_config(cls, conn: 'ClientConnection') -> 'AntiCheat':
        provider, mode = settings(conn.server.config)
        cfg = conn.server.config.get('anticheat') or {}
        validator = VALIDATORS[provider]() if provider in VALIDATORS else None
        if cfg.get('validator') in ('ggauth', 'ggauth50'):
            from gunbound.game.ggauth50 import from_config
            validator = from_config(conn.server, cfg)
        capture = capture_query(cfg) if mode == 'capture' else None
        return cls(conn, provider, mode, validator, float(cfg.get('requery', REQUERY_SECONDS)),
                   float(cfg.get('deadline', DEADLINE_SECONDS)), capture, str(cfg.get('capture_out', CAPTURE_OUT)))

    @property
    def active(self) -> bool:
        return self.mode != 'off' and not self.closed

    def log(self, step: str, op: int | None = None, **fields) -> None:
        extra = ''.join(f" {k}={v}" for k, v in fields.items())
        opcode = f" op=0x{op:04X}" if op is not None else ''
        print(f"[anticheat] sess={self.sid} prov={self.provider} mode={self.mode} step={step}{opcode}{extra}")

    def start(self) -> None:
        """Depois do 0x1012 OK (o v584 manda o SendUserID ao GameMon nesse ponto)."""
        if not self.active:
            return
        self.started = time.monotonic()
        self.log('start', validator='sim' if self.validator else 'nenhum')
        if self.mode == 'capture':
            self._send(PROFILES['gameguard'][0], Query(b'', self.capture))   # uma vez por sessão, sem nova pergunta
        elif self.validator is not None:
            self.ask()
        if self.mode == 'required':
            self._arm_deadline()

    def ask(self) -> None:
        if not self.active or self.validator is None:
            return
        if self.asking or self.pending:
            return
        self.asking = True
        self._task(self._ask())

    def _task(self, coroutine):
        task = asyncio.get_running_loop().create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def _ask(self):
        try:
            for ex in PROFILES[self.provider]:
                result = self.validator.query(ex)
                query = await result if inspect.isawaitable(result) else result
                if self.active:
                    self._send(ex, query)
        except Exception:
            await self._reject(None, b'', 'validador_indisponivel')
        finally:
            self.asking = False

    def _send(self, ex: Exchange, query: Query) -> None:
        if len(query.wire) != ex.challenge_len:
            self.log('challenge', ex.challenge, result='validador_tamanho_errado', len=len(query.wire))
            return
        self.pending[ex.answer] = (query, time.monotonic())
        asyncio.get_running_loop().create_task(self.conn.on_send(Packet.new(ex.challenge).raw(query.wire)))
        self.log('challenge', ex.challenge, len=len(query.wire), sha=digest(query.wire))

    async def on_answer(self, op: int, body: bytes) -> None:
        known = ANSWERS.get(op)
        if not self.active:
            self.log('answer', op, len=len(body), result='ignorado_off')
            return
        if known is None or known[0] != self.provider:
            return await self._reject(op, body, 'opcode_de_outro_provider')
        exchange = known[1]
        asked = self.pending.pop(op, None)
        took = f"{(time.monotonic() - asked[1]) * 1000:.0f}" if asked else '-'
        if len(body) not in exchange.answer_lens:
            return await self._reject(op, body, 'tamanho_invalido', dur_ms=took)
        if asked is None:
            return await self._reject(op, body, 'sem_pergunta_pendente')  # replay ou resposta não pedida
        if self.mode == 'capture':
            self._record(op, asked[0].wire, body, took)
            return
        if self.validator is None:
            self.log('answer', op, len=len(body), sha=digest(body), dur_ms=took, result='nao_verificado')
            return
        try:
            result = self.validator.check(exchange, asked[0].internal, body)
            valid = await result if inspect.isawaitable(result) else result
        except Exception:
            return await self._reject(op, body, 'validador_indisponivel', dur_ms=took)
        if not valid:
            return await self._reject(op, body, 'invalido', dur_ms=took)
        self.log('answer', op, len=len(body), sha=digest(body), dur_ms=took, result='ok')
        if self.mode == 'required':
            self._arm_deadline()
        result = RESULT_OK.get(self.provider)
        if result is not None:
            await self.conn.on_send(Packet.new(result, rtc=0))
            self.log('result', result, rtc=0)
        self._later(self.requery, self.ask)

    def _record(self, op: int, query: bytes, answer: bytes, took: str) -> None:
        """Capture: par do fio para conferir offline (gg-server-emu/tools/check_pair_files.py). Sem usuário."""
        row = {'time': time.strftime('%Y-%m-%dT%H:%M:%S'), 'sess': self.sid, 'query_op': f"0x{op - 1:04X}",
               'query': query.hex(), 'answer_op': f"0x{op:04X}", 'answer': answer.hex(), 'dur_ms': took}
        try:
            path = Path(self.capture_out)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row) + '\n')
            result = 'capturado'
        except OSError as e:
            result = f"falha_ao_gravar({e.__class__.__name__})"
        self.log('answer', op, len=len(answer), sha=digest(answer), dur_ms=took, result=result, out=self.capture_out)

    async def _reject(self, op: int, body: bytes, why: str, **fields) -> None:
        self.log('answer', op, len=len(body), sha=digest(body), result=why, **fields)
        if self.mode == 'required':
            self.log('disconnect', reason=why)
            await self.conn.close()

    def _arm_deadline(self) -> None:
        for t in self.timers:
            t.cancel()
        self.timers.clear()
        self._later(self.deadline, self._expire)

    def _later(self, seconds: float, fn) -> None:
        if self.active:
            self.timers.append(asyncio.get_running_loop().call_later(seconds, fn))

    def _expire(self) -> None:
        if not self.active:
            return
        self.log('timeout', after_s=f"{time.monotonic() - self.started:.0f}", pendentes=len(self.pending))
        if self.mode == 'required':
            self.log('disconnect', reason='timeout')
            asyncio.get_running_loop().create_task(self.conn.close())

    def close(self) -> None:
        if self.closed:
            return
        for t in self.timers:
            t.cancel()
        self.timers.clear()
        if self.mode != 'off':
            self.log('close', pendentes=len(self.pending))
        self.closed = True
        current = asyncio.current_task()
        for task in tuple(self.tasks):
            if task is not current:
                task.cancel()
        close = getattr(self.validator, 'close', None)
        if close is not None:
            async def cleanup():
                try:
                    result = close()
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    self.log('validator_close', result='indisponivel')
            self._task(cleanup())
