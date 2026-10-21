"""
Bot na sala: um jogador sem socket (BotConn) num slot da sala, sempre pronto. Não existe no banco.
Comandos (texto do 0x5100, para o mestre da sala; docs/Bots.md):
  /bot add [patente] [mobile]   sem patente: equilibra os times (ou a média da sala no Solo); mobile só GM com gm_mobile
  /bot remove [nome|all]        sem nome: o último que entrou
Config do game server: bots: {enabled, gm_mobile, max, reward, skill: {...}}.
"""
from __future__ import annotations
import itertools
import random
import re
from gunbound.bot import profiles, skill
from gunbound.game import phase, room_packets as rp
from gunbound.game.protocol.enums import ServerPacket

_ids = itertools.count(1 << 32)  # fora da faixa dos ClientConnection (id(self) & 0xFFFFFFFF)
SYLLABLES = ('ka', 'ro', 'mi', 'zu', 'te', 'na', 'lo', 'vi', 'ga', 're', 'xo', 'bu', 'ny', 'da', 'ki', 'po', 'se', 'ta')
CASH_GOLD = 100     # 1 cash vale isso em gold na hora de medir o quanto o equipamento é "caro"
REWARD = 0.0        # fator do gold/GP de quem joga com bot (0 = nada, contra farm)


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
        self.addr = f"bot:{nick}"
        self.data = {'profile': {'Id': None, 'Nickname': nick, 'Gender': gender, 'Authority': 0},
                     'game': game, 'avatar': avatar}

    async def on_send(self, packet):
        pass

    async def close(self):
        pass


def bot_name(taken: set[str], rng=random) -> str:
    for _ in range(50):
        name = ''.join(rng.choice(SYLLABLES) for _ in range(rng.randint(2, 3))).capitalize()
        if rng.random() < 0.4:
            name += str(rng.randint(1, 99))
        if name.lower() not in taken:
            return name[:12]
    return f"Bot{rng.randint(100, 999)}"


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


def auto_level(others: list, team_mode: bool, team: int) -> float:
    """Time: o que falta para igualar a força somada do outro time. Solo (ou sem adversário): a média da sala."""
    if team_mode:
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
    player = await room.join(bot)
    if player is None:
        return "BOT>> A sala está cheia."
    others = [p for p in room.players.values() if p is not player]
    bot.n = skill.normalize(layout, grade) if grade is not None else auto_level(others, room.is_team_mode(), player.team)
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
    name = profiles.BY_PHASE[layout][player.tank1].name
    return f"BOT>> {bot.data['profile']['Nickname']} entrou: patente {level}, {name}, time {'AB'[player.team]}."


async def remove(room, who: str) -> str:
    bots = sorted((p for p in room.players.values() if is_bot(p.conn)), key=lambda p: p.conn.id)
    if who.lower() == 'all':
        targets = bots
    elif who:
        targets = [p for p in bots if p.conn.data['profile']['Nickname'].lower() == who.lower()]
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
        return "BOT>> Use /bot add [patente] [mobile] ou /bot remove [nome|all]."
    layout = type(phase.of(conn)).__name__
    grade = tank = None
    if args and re.fullmatch(r'-?\d+', args[0]):
        low, high, _ = skill.GRADE_SCALE[layout]
        grade = int(args.pop(0))
        if not min(low, high) <= grade <= max(low, high):
            return f"BOT>> Patente de {min(low, high)} a {max(low, high)} nesta versão."
    if args:
        from gunbound.game.protocol.gm_commands import is_gm
        if not (cfg(conn.server.config).get('gm_mobile') and is_gm(conn)):
            return "BOT>> Escolher o mobile é só para GM."
        tank = find_mobile(layout, ' '.join(args))
        if tank is None:
            return f"BOT>> Mobile '{' '.join(args)}' não existe nesta versão."
    return await add(conn, room, grade, tank, inventory_repository)


def reward(room, player, gold: int, gp: int, server_config) -> tuple[int, int] | None:
    """Prêmio de partida: bot não recebe (None); com bot na sala, os outros recebem `bots.reward` (padrão 0)."""
    if is_bot(player.conn):
        return None
    if any(is_bot(p.conn) for p in room.players.values()):
        factor = float(cfg(server_config).get('reward', REWARD))
        return int(gold * factor), int(gp * factor)
    return gold, gp
