"""
Bot na sala: um jogador sem socket (BotConn) num slot da sala, sempre pronto. Não existe no banco.
Comandos (texto do 0x5100, para o mestre da sala; docs/Bots.md):
  /bot add [patente|auto] [mobile|auto]   sem patente (ou auto): equilibra os times (ou a média da sala no Solo);
                                          mobile só GM com gm_mobile; auto = aleatório
  /bot remove [nome|all]        sem nome: o último que entrou
Config do game server: bots: {enabled, gm_mobile, max, reward, skill: {...}}.
"""
from __future__ import annotations
import asyncio
import itertools
import random
import re
import struct
from Crypto.Cipher import AES
from gunbound.bot import profiles, skill
from gunbound.game import phase, room_packets as rp
from gunbound.game.protocol.enums import ServerPacket

_ids = itertools.count(1 << 32)  # fora da faixa dos ClientConnection (id(self) & 0xFFFFFFFF)
SYLLABLES = ('ka', 'ro', 'mi', 'zu', 'te', 'na', 'lo', 'vi', 'ga', 're', 'xo', 'bu', 'ny', 'da', 'ki', 'po', 'se', 'ta')
CASH_GOLD = 100     # 1 cash vale isso em gold na hora de medir o quanto o equipamento é "caro"
REWARD = 0.5        # fator do gold/GP de quem joga com bot (metade; 0 = nada, contra farm)
SUFFIX = '[BOT]'    # no apelido (12 bytes no fio), para ninguém confundir com gente
AUTO = ('auto', 'random')


def cfg(server_config) -> dict:
    return server_config.get('bots') or {}


def enabled(conn) -> bool:
    return bool(cfg(conn.server.config).get('enabled'))


def is_bot(conn) -> bool:
    return getattr(conn, 'bot', False)


class BotConn:
    """O mínimo de ClientConnection que a sala e os pacotes de sala usam; tudo que mandam para ele é descartado."""
    bot = True
    closing = False
    channel = None

    def __init__(self, server, nick: str, gender: int, game: dict, avatar: list[int], n: float):
        self.id, self.server, self.room, self.n = next(_ids), server, None, n
        self.seq: dict[int, int] = {}  # seq do frame P2P por slot de destino
        self.counter, self.whose, self.tail, self.last_hit = 0, -1, b'', -1  # turno (gunbound/bot/match.py)
        self.seen, self.terrain, self.layout = {}, None, ''  # tiro (gunbound/bot/match.py, aim.py)
        self.addr = f"bot:{nick}"
        self.data = {'profile': {'Id': None, 'Nickname': nick, 'Gender': gender, 'Authority': 0},
                     'game': game, 'avatar': avatar}

    async def on_send(self, packet):
        pass

    async def close(self):
        pass


def bot_name(taken: set[str], rng=random) -> str:
    base = 12 - len(SUFFIX)
    for _ in range(50):
        name = ''.join(rng.choice(SYLLABLES) for _ in range(rng.randint(2, 3))).capitalize()
        if rng.random() < 0.4:
            name += str(rng.randint(1, 99))
        name = name[:base] + SUFFIX
        if name.lower() not in taken:
            return name
    return f"Bot{rng.randint(100, 999)}{SUFFIX}"


# P2P da partida pelo túnel 0x4501 (docs/Bots.md): frame = u16 hdr (0x8000 dado | tamanho), u8 seq, u8 soma do cifrado,
# AES-128-ECB(u16 tipo + corpo, zeros até 16). Chave = u16 índice do servidor no broker + "comsik" + u16 sala + cauda.
TAIL = bytes.fromhex('d222eafaee3a')
LOAD_STEP, LOAD_DONE = 0x8201, 0x82FF  # progresso (u8 slot, u8 etapa 1..3) e carregou: captura v584 de 2 clientes
# Sala de espera: o "pronto" não passa pelo servidor; quem não é mestre manda 0x8102 u8 (3 pronto, 1 presente) pelo
# túnel (captura; envio em 0x50923a, ReadyMode do v584). 0x8100 é o ping ("250ms").
READY = 0x8102
# Tela de resultado: cada cliente manda 0x8103 (vazio) pelo túnel ao clicar OK, e quem já clicou fica em "espere os
# outros usuários" até receber o de todos (captura de 2 humanos e do v584). O 0xc30c do mestre chega ao bot com a
# partida já fechada (room.game None), então o servidor manda o OK dos bots depois do 0x4413.
RESULT_OK = 0x8103
# 0x8400 (v584): dados do jogador que cada cliente manda aos outros no começo da partida (emissor 0x50e710, receptor
# 0x42d927). Do byte 57 em diante o humano manda zeros: licença de mobile (118), bônus de dano (122..130), pct de dano
# e cratera (163/165; <= -50 zera os dois, 0x4274f0) e avatar 4/5 (179/181). Sem o pacote o cliente fica com o que
# tinha na memória para o slot desde a entrada na sala (0x4d93b0 zera), então o bot manda o dele com os zeros.
PLAYER_INFO = 0x8400
INFO_SIZE = 0x100
RESULT_OK_WAIT = 3.0


def p2p_frame(key: bytes, seq: int, kind: int, body: bytes) -> bytes:
    plain = struct.pack('<H', kind) + body
    cipher = AES.new(key, AES.MODE_ECB).encrypt(plain.ljust(-(-len(plain) // 16) * 16, b'\x00'))
    return struct.pack('<HBB', 0x8000 | (4 + len(cipher)), seq & 0xFF, sum(cipher) & 0xFF) + cipher


def p2p_key(room, server) -> bytes:
    return struct.pack('<H', server.index) + b'comsik' + struct.pack('<H', room.id) + TAIL


async def p2p_send(room, bot_player, kind: int, body: bytes) -> None:
    key = p2p_key(room, bot_player.conn.server)
    for p in list(room.players.values()):
        if is_bot(p.conn):
            continue
        seq = bot_player.conn.seq.get(p.slot, 0)
        bot_player.conn.seq[p.slot] = seq + 1
        frame = p2p_frame(key, seq, kind, body)
        if path := bot_player.conn.server.config.get('tunnel_log'):
            from gunbound.game.protocol.game_play import log_tunnel  # import tardio: game_play importa este módulo
            log_tunnel(path, room, bot_player, bytes([p.slot]), frame)
        await p.conn.on_send(rp.tunnel(bot_player.slot, frame))


async def announce_ready(room, delay: float = 0.0) -> None:
    """Todo bot da sala avisa os humanos que está pronto (ao entrar e quando eles voltam do resultado)."""
    await asyncio.sleep(delay)
    for p in [p for p in room.players.values() if is_bot(p.conn)]:
        p.conn.seq.clear()  # sala nova para o P2P, como no começo da partida
        await p2p_send(room, p, READY, bytes([3]).ljust(14, b'\x00'))


async def confirm_result(room, delay: float = RESULT_OK_WAIT) -> None:
    """Todo bot da sala "clica OK" na tela de resultado."""
    await asyncio.sleep(delay)
    for p in [p for p in room.players.values() if is_bot(p.conn)]:
        await p2p_send(room, p, RESULT_OK, bytes(14))


async def load(room, delay: float = 0.3) -> None:
    """Depois do 0x3432: cada bot avisa as 3 etapas do carregamento e o fim, como um cliente (senão a tela trava em 0%).
    O turno vem depois, pelos frames do mestre (gunbound/bot/match.py)."""
    bots = [p for p in room.players.values() if is_bot(p.conn)]
    for p in bots:
        p.conn.seq.clear()
        p.conn.counter, p.conn.whose, p.conn.tail, p.conn.last_hit = 0, -1, b'', -1
        p.conn.seen, p.conn.terrain, p.conn.shots, p.conn.last = {}, None, 0, None
        p.conn.weather, p.conn.event, p.conn.joker, p.conn.pos, p.conn.items = [], None, None, None, None
    if any(phase.is_v584(p.conn) for p in room.players.values() if not is_bot(p.conn)):
        for p in bots:
            await p2p_send(room, p, PLAYER_INFO, player_info(p))
    for step in (1, 2, 3):
        await asyncio.sleep(delay)
        for p in bots:
            await p2p_send(room, p, LOAD_STEP, bytes([p.slot, step]).ljust(14, b'\x00'))
    for p in bots:
        await p2p_send(room, p, LOAD_DONE, bytes(14))


def player_info(p) -> bytes:
    """Corpo do 0x8400 como o do humano (captura v584 de 21/10): apelido (16), apelido de novo (12; [INCERTO] guild),
    u16 0, u32 [INCERTO] id, u32 x4 (o humano manda 2, 2, 0, 2: [INCERTO] patente), u16 0x1c ([INCERTO], igual nos 2
    humanos), sinal (1 = positivo) + u32 GP, zeros."""
    nick = p.conn.data['profile']['Nickname'].encode('latin-1')
    grade = int(p.conn.data['game'].get('TotalGrade') or 0)
    score = int(p.conn.data['game'].get('TotalScore') or 0)
    body = (nick[:15].ljust(16, b'\x00') + nick[:12].ljust(12, b'\x00') + struct.pack('<HI4IHBI', 0, 0, grade, grade, 0, grade,
                                                                                         0x1c, int(score >= 0), abs(score)))
    return body.ljust(INFO_SIZE, b'\x00')


def pick_avatar(slots: list[list[tuple[int, int]]], n: float, rng=random) -> list[int]:
    """slots = por tipo (cabeça, corpo, bandeira) a lista (item, valor) do mais barato ao mais caro. Quanto maior a
    patente, mais chance de vestir algo e mais caro (percentil ~n, com variação)."""
    out = []
    for items in slots:
        if not items or rng.random() > 0.4 + 0.6 * n:
            continue
        pos = min(1.0, max(0.0, n + rng.uniform(-0.15, 0.15)))
        out.append(items[round(pos * (len(items) - 1))][0])
    return out


def strength(p) -> float:
    if is_bot(p.conn):
        return p.conn.n
    layout = type(phase.of(p.conn)).__name__
    return skill.normalize(layout, int((p.conn.data.get('game') or {}).get('TotalGrade') or 0))


def auto_level(others: list, team: int) -> float:
    """O que falta para igualar a força somada do outro time (todo modo é time A x B, o Solo também); sem adversário,
    a média da sala."""
    mine = sum(strength(p) for p in others if p.team == team)
    theirs = [strength(p) for p in others if p.team != team]
    if theirs:
        return min(1.0, max(0.0, sum(theirs) - mine))
    return sum(strength(p) for p in others) / len(others) if others else 0.5


def find_mobile(layout: str, name: str) -> int | None:
    key = re.sub(r'[^a-z0-9]', '', name.lower())
    tanks = phase.load(layout).tanks
    return next((i for i, m in profiles.BY_PHASE[layout].items()
                 if i in tanks and re.sub(r'[^a-z0-9]', '', m.name.lower()) == key), None)


async def avatar_pool(inventory_repository, gender: int) -> list[list[tuple[int, int]]]:
    from gunbound.game.protocol.wcs2.events import avatar_range
    pools = []
    for kind in ('head', 'body', 'flag'):
        lo, hi = avatar_range(kind, gender)
        rows = await inventory_repository.avatar_prices(lo, hi)
        pools.append(sorted(((item, gold + cash * CASH_GOLD) for item, gold, cash in rows), key=lambda r: r[1]))
    return pools


async def add(conn, room, grade: int | None, tank: int | None, inventory_repository, rng=random) -> str:
    layout = type(phase.of(conn)).__name__
    bots = cfg(conn.server.config)
    if sum(is_bot(p.conn) for p in room.players.values()) >= int(bots.get('max', 7)) or room.is_full():
        return "BOT>> A sala está cheia."
    gender = rng.getrandbits(1)
    taken = {p.conn.data['profile']['Nickname'].lower() for p in room.players.values()}
    bot = BotConn(conn.server, bot_name(taken, rng), gender, {}, [], 0.5)
    bot.layout = layout
    player = await room.join(bot)
    if player is None:
        return "BOT>> A sala está cheia."
    others = [p for p in room.players.values() if p is not player]
    bot.n = skill.normalize(layout, grade) if grade is not None else auto_level(others, player.team)
    level = skill.denormalize(layout, bot.n)
    bot.data['game'] = {'Guild': '', 'TotalGrade': level, 'SeasonGrade': level, 'CountryGrade': level,
                        'Country': (conn.data.get('game') or {}).get('Country') or 0}
    bot.data['avatar'] = pick_avatar(await avatar_pool(inventory_repository, gender), bot.n, rng)
    pool = [t for t in phase.of(conn).random_tanks if t in profiles.BY_PHASE[layout]]
    player.tank1 = tank if tank is not None else rng.choice(pool)
    player.tank2 = rng.choice(pool)
    player.ready = True
    room.room_manager.notify_lobby(room, rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_PLAYERS, room).u8(room.player_count()))
    await room.broadcast(rp.player_joined(player), excepts=[bot.id])
    await announce_ready(room)
    name = profiles.BY_PHASE[layout][player.tank1].name
    return f"BOT>> {bot.data['profile']['Nickname']} entrou: patente {level}, {name}, time {'AB'[player.team]}."


async def remove(room, who: str) -> str:
    bots = sorted((p for p in room.players.values() if is_bot(p.conn)), key=lambda p: p.conn.id)
    if who.lower() == 'all':
        targets = bots
    elif who:
        names = (who.lower(), (who + SUFFIX).lower())
        targets = [p for p in bots if p.conn.data['profile']['Nickname'].lower() in names]
    else:
        targets = bots[-1:]
    for p in targets:
        await room.room_manager.leave(p.conn)
    return f"BOT>> {len(targets)} bot(s) removido(s)." if targets else "BOT>> Nenhum bot encontrado."


async def command(conn, text: str, inventory_repository) -> str:
    """/bot add|remove. Só o mestre de uma sala aguardando."""
    room = conn.room
    if room is None or not room.is_master(conn) or not room.is_waiting() or getattr(room, 'auto', False) \
            or room.options.stage is not None:
        return "BOT>> Só o mestre de uma sala comum aguardando usa /bot."
    parts = text.split()[1:]
    sub, args = (parts[0].lower(), parts[1:]) if parts else ('', [])
    if sub == 'remove':
        return await remove(room, ' '.join(args))
    if sub != 'add':
        return "BOT>> Use /bot add [patente|auto] [mobile|auto] ou /bot remove [nome|all]."
    layout = type(phase.of(conn)).__name__
    grade = tank = None
    if args and args[0].lower() in AUTO:
        args.pop(0)
    elif args and re.fullmatch(r'-?\d+', args[0]):
        low, high, _ = skill.GRADE_SCALE[layout]
        grade = int(args.pop(0))
        if not min(low, high) <= grade <= max(low, high):
            return f"BOT>> Patente de {min(low, high)} a {max(low, high)} nesta versão."
    if args and ' '.join(args).lower() in AUTO:
        args = []
    if args:
        from gunbound.game.protocol.gm_commands import is_gm
        if not (cfg(conn.server.config).get('gm_mobile') and is_gm(conn)):
            return "BOT>> Escolher o mobile é só para GM."
        tank = find_mobile(layout, ' '.join(args))
        if tank is None:
            return f"BOT>> Mobile '{' '.join(args)}' não existe nesta versão."
    return await add(conn, room, grade, tank, inventory_repository)


def reward(room, player, gold: int, gp: int, server_config) -> tuple[int, int] | None:
    """Prêmio de partida: bot não recebe (None); com bot na sala, os outros recebem `bots.reward` (padrão 0,5)."""
    if is_bot(player.conn):
        return None
    if any(is_bot(p.conn) for p in room.players.values()):
        factor = float(cfg(server_config).get('reward', REWARD))
        return int(gold * factor), int(gp * factor)
    return gold, gp
