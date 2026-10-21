"""
Bot na partida (docs/Bots.md, estágios 1a, 1b e 2): responde o ciclo de turno do P2P como um cliente, atira no turno
dele (2; passa a vez se não tem mapa, 1a) e morre quando o mestre manda (1b). Regras da captura v584 1x1
(tests/fixtures/bot_turn_replay.txt) e do cliente:
o mestre (0x42e798) só espera um 0xc302 de cada slot por fase (0f início/passe, 0e tiro, 02 pronto) e não lê o
contador; 0xc40a e 0xc309 caem no default do despachante (0x4dd8a0), vão só para imitar.
Morte: cada cliente calcula o HP de todos os tanques. Na escolha do próximo turno (0x4f5aa0) o mestre manda 0xc312
(u8 slot) para quem tem HP <= 0 ou y >= 9000 e não se declarou; o cliente responde 0xc314 (vazio); o mestre confere o
tanque de quem respondeu e manda 0xc315 (u8 slot); o dono manda 0xc304 (u32 causa, u8 matador) e o TCP 0x4100
(0x4e0596). Então o servidor não calcula dano: o bot segue esse caminho.
Tiro: 0x8006 (u16 x, u16 y, 00 01), ~1 s depois o 0xc400, e quando o tiro termina o 0c302 0e com o delay em +5.
Quem recebe o 0xc400 (0x4e075b) põe o atirador em x/y e simula o tiro (gunbound/bot/aim.py).
"""
from __future__ import annotations
import asyncio
import math
import random
import struct
from pathlib import Path
from Crypto.Cipher import AES
from gunbound.bot import aim, profiles, skill
from gunbound.bot.room import cfg, is_bot, p2p_key, p2p_send
from gunbound.game import phase

START, NEXT, PASS, REPORT, SYNC, DEATH, POS, DEATH_ACK = 0x8600, 0xC300, 0xC301, 0xC302, 0xC303, 0xC304, 0xC40A, 0xC309
CHECK, CHECK_ACK, KILL = 0xC312, 0xC314, 0xC315
AIM, SHOT, MOVE = 0x8006, 0xC400, 0x8402
SHOTS = (0xC400, 0xC409)
SS = 0xC409         # SS: o mesmo corpo do 0xc400 (0x4e0cc9 pula o byte do tiro 2 e liga +0x1a8/+0x1ac)
PLACES = {POS: '<II', MOVE: '<HH', SHOT: '<HH', AIM: '<HH'}  # onde cada humano está
PASS_DELAY = 9000   # u16 do C301, soma no delay do slot (0x41c3b0); 0xffff/0xea60 não somam e o bot ganharia todo turno
SHOT_DELAY = 8900   # shortcut: delay do 0e do atirador como o da captura (8400..8900); o real vem do mobile e do tempo
SHOT_WAIT = 3.0     # humanos mandam o 0e 1,3..3,3 s depois do tiro; atrasado é seguro, o mestre só espera
TURN_WAIT = 3.0     # o bot "pensa" antes de agir
AIM_WAIT = 1.0      # 0x8006 -> 0xc400, como os humanos
SHOOTS = {'WCS2'}   # tiro estudado no v584; nas outras fases o bot passa a vez
SHOT2 = 0.4         # chance do tiro 2 quando ele voa como o 1 (profiles: special=False)
SS_EVERY = 5        # shortcut: o SS fica pronto a cada 5 tiros do bot; o do cliente enche pelo dano, falta mapear
# clima do v584 (docs/Bots.md): código do evento do 0xc300 -> coluna; slots do bloco na ordem do 0x428410
EVENTS = {0: 'force', 1: 'tornado', 2: 'electric', 7: 'blackforce', 8: 'mirror'}  # 9 = coringa
SLOTS = ('force', 'tornado', 'electric', 'blackforce', 'mirror', 'joker')
JOKER = ('force', 'tornado', 'electric', 'blackforce', 'mirror')  # tipo do coringa (0x44a8c4)
TIEBREAK = 0.02     # px de erro da mira que valem 1 px de distância na escolha do alvo
REPEAT = 5          # px: o último tiro que acertou se repete se nem o bot nem o alvo andaram mais que isso
V584_POWER = 5      # força do 0xc400 do v584 = 5x a do antigo (tiros do admin, até 2200); aim.py usa a escala antiga
DIES_NOW = 0x10     # 0xc304: com o bit, quem recebe tira o tanque na hora (0x4df66b, y = 10000); o dono que se vê morto
                    # manda causa | 0x10 (0x482955). Sem o bit o mestre ainda o acha vivo e manda outro 0xc312
_tasks: set[asyncio.Task] = set()
_warned: set[str] = set()


async def on_frame(room, bot, sender, frame: bytes) -> None:
    """Frame do túnel 0x4500 de um humano para o slot do bot: decifra e reage."""
    if len(frame) < 20 or not frame[1] & 0x80:
        return
    cipher = frame[4:struct.unpack_from('<H', frame)[0] & 0x3fff]
    plain = AES.new(p2p_key(room, bot.conn.server), AES.MODE_ECB).decrypt(cipher[:len(cipher) // 16 * 16])
    if len(plain) >= 2:
        await react(room, bot, sender, struct.unpack_from('<H', plain)[0], plain[2:])


async def react(room, bot, sender, kind: int, body: bytes) -> None:
    conn, game = bot.conn, room.game
    master = room.player(room.owner)
    from_master = master is not None and sender.slot == master.slot
    if kind in PLACES and len(body) >= struct.calcsize(PLACES[kind]):
        conn.seen[sender.slot] = struct.unpack_from(PLACES[kind], body)
    if kind == START and from_master:
        await prepare(room, bot)
        await report(room, bot, 0x0f)
    elif kind in SHOTS:
        conn.last_hit = sender.slot  # o cliente guarda quem acertou por último (+0x2a4); aqui, quem atirou por último
        craters(conn, body)
        later(room, bot, SHOT_WAIT, report(room, bot, 0x0e, game))
    elif kind == PASS:
        await report(room, bot, 0x0f)
    elif kind == NEXT and from_master and len(body) >= 3:
        conn.whose, conn.counter, conn.tail = body[0], struct.unpack_from('<H', body, 1)[0] + 1, body[3:]
        if getattr(conn, 'v584', False):
            update_weather(conn, body[3:])
        await report(room, bot, 0x02)
    elif kind == SYNC and from_master and body[:1] == b'\x02' and conn.whose == bot.slot:
        conn.whose = -1
        later(room, bot, TURN_WAIT, take_turn(room, bot, game))
    elif kind == CHECK and from_master and bot.alive:  # todo cliente responde (0x4e0425 não lê o slot)
        await send(room, bot, CHECK_ACK, b'')
    elif kind == KILL and from_master and body[:1] == bytes([bot.slot]) and bot.alive:
        await die(room, bot)
    elif kind == DEATH and len(body) >= 5:
        await send(room, bot, DEATH_ACK, bytes([sender.slot]) + body[:5])


async def prepare(room, bot) -> None:
    """Terreno da partida e o chão sob o spawn (o cliente solta o tanque até o chão)."""
    conn = bot.conn
    conn.terrain = None
    conn.v584 = any(phase.is_v584(p.conn) for p in room.players.values() if not is_bot(p.conn))
    if getattr(conn, 'layout', None) in SHOOTS:
        conn.terrain = await terrain(room, conn)


async def terrain(room, conn) -> aim.Terrain | None:
    """Mapa da partida no cliente dos humanos: os importados por tools/import_maps.py (bots.maps) ou, sem eles, o
    graphics.xfs do S1. Sem mapa o bot só passa a vez."""
    if room.game is None:
        return None
    c = cfg(conn.server.config)
    side = (room.options.settings >> 16) & 3
    try:
        return await asyncio.to_thread(aim.load_map, room.game.map, side, 'v584' if conn.v584 else 's1',
                                       aim.ROOT / Path(c.get('maps') or aim.MAPS),
                                       aim.ROOT / Path(c.get('graphics_xfs') or aim.DEFAULT_XFS))
    except Exception as e:  # arquivo ausente ou ilegível: avisa uma vez
        if str(e) not in _warned:
            _warned.add(str(e))
            print(f"[BOT] terreno do mapa {room.game.map} lado {side}: {e}")
        return None


def place(room, bot, slot: int) -> tuple[int, int]:
    """Onde está o tanque do slot: o último x/y que ele mandou, senão o spawn no chão (o do bot cai nas crateras,
    que aqui têm raio fixo; o cliente pode pôr o tanque um pouco acima ou abaixo)."""
    conn = bot.conn
    if slot != bot.slot and slot in conn.seen:
        return conn.seen[slot]
    x, y = room.game.spawns.get(slot, (0, 0)) if room.game else (0, 0)
    ground = conn.terrain.ground(x, y) if conn.terrain else None
    return x, ground if ground is not None else y


def craters(conn, body: bytes) -> None:
    """Impactos do 0xc400 (u8 n @28, @30 no v584, + n x (u8 tipo, u16 x, u16 y)) cavam o terreno do bot."""
    at = 30 if getattr(conn, 'v584', False) else 28
    if conn.terrain is None or len(body) <= at:
        return
    for i in range(min(body[at], (len(body) - at - 1) // 5)):
        _, x, y = struct.unpack_from('<BHH', body, at + 1 + 5 * i)
        conn.terrain.carve(x, y)


async def report(room, bot, phase: int, game=None, delay: int = 0) -> None:
    """C40A (posição) + C302 (fase, u32 contador, u32 delay; o delay só é lido do atirador no 0e)."""
    if room.game is None or (game is not None and room.game is not game):
        return
    x, y = place(room, bot, bot.slot)
    await send(room, bot, POS, struct.pack('<II', x, y))
    await send(room, bot, REPORT, struct.pack('<BII', phase, bot.conn.counter, delay))


async def take_turn(room, bot, game) -> None:
    if room.game is not game:
        return
    try:
        plan = aim_at(room, bot)
        if plan is not None:
            return await shoot(room, bot, game, *plan)
    except Exception as e:  # o turno tem que terminar, senão o mestre espera para sempre
        print(f"[BOT] tiro de {bot.conn.data['profile']['Nickname']}: {e!r}")
    await pass_turn(room, bot, game)


async def pass_turn(room, bot, game) -> None:
    """C301 = 01 + u16 delay + estado do próximo turno (o cliente copia 0x60 bytes; o mestre ecoa no C300)."""
    if room.game is not game:
        return
    await send(room, bot, PASS, b'\x01' + struct.pack('<H', PASS_DELAY) + bot.conn.tail)
    await report(room, bot, 0x0f)


def update_weather(conn, block: bytes) -> None:
    """Bloco do 0xc300 do v584 (0x428410): vento (u8, s16), u8, u8, u8 evento da rodada do próximo turno, 6 slots ff ou
    (00 | tipo do coringa, u8 largura, u16 x). No começo do turno o cliente apaga o clima que não é do evento atual
    (0x451200); o evento deste turno veio no 0xc300 anterior. Coluna nova perto de outra igual (x +- w/4 + 5) funde:
    largura max * 1,5 e x na média (o espelho fica onde estava)."""
    if len(block) < 6:
        return
    cols, event = getattr(conn, 'weather', []), getattr(conn, 'event', None)
    if event is not None:
        now = getattr(conn, 'joker', None) if event == 9 else EVENTS.get(event)
        cols = [c for c in cols if c[0] == now]
    conn.event, i = block[5], 6
    for slot in SLOTS:
        if i >= len(block) or block[i] == 0xff:
            i += 1
            continue
        if i + 4 > len(block):
            break
        kind, w, x = slot, block[i + 1], struct.unpack_from('<H', block, i + 2)[0]
        if slot == 'joker':  # o cliente limpa tudo antes do coringa (0x4511b0)
            kind = conn.joker = JOKER[block[i]] if block[i] < len(JOKER) else None
            cols = []
        i += 4
        if kind is None:
            continue
        near = next((n for n, c in enumerate(cols) if c[0] == kind and x - w // 4 - 5 <= c[1] <= x + w // 4 + 5), None)
        if near is None:
            cols.append((kind, x, w))
        else:
            _, ox, ow = cols[near]
            cols[near] = (kind, ox if kind == 'mirror' else (ox + x) // 2, max(ow, w) * 15 // 10)
    conn.weather = cols


def wind(conn) -> tuple[int, int]:
    """Vento do turno no C300: u8 força, u16 ângulo (o 0xc400 leva o mesmo; quem recebe grava em G+0x283dc/e0)."""
    return (conn.tail[0], struct.unpack_from('<H', conn.tail, 1)[0]) if len(conn.tail) >= 3 else (0, 0)


def pick_kind(conn, tank: int, rng=random):
    """Tiro 1, 2 ou 'ss'. O 2 só quando voa como o 1 (Nak cava, Trico orbita... a mira não simula esses)."""
    conn.shots = getattr(conn, 'shots', 0) + 1
    if conn.shots % SS_EVERY == 0:
        return 'ss'
    return 2 if not profiles.shot(conn.layout, tank, 2).special and rng.random() < SHOT2 else 1


def aim_at(room, bot, rng=random) -> tuple[int, int, tuple[int, int] | None, object] | None:
    """(ângulo, força, impacto, tiro) no inimigo mais fácil: simula o melhor tiro em cada um e fica com o menor erro
    (a distância só desempata); erra a força pela chance de acerto (gunbound/bot/skill.py).
    Se o último tiro acertou e ninguém andou, repete no mesmo alvo: com o mesmo vento, o mesmo ângulo e a força 1..2%
    diferente; com outro vento, a mira nova, sem sortear erro."""
    conn, t = bot.conn, getattr(bot.conn, 'terrain', None)
    if t is None:
        return None
    me = place(room, bot, bot.slot)
    others = [p for p in room.players.values() if p is not bot and p.alive]
    enemies = [p for p in others if p.team != bot.team or not room.is_team_mode()]
    if not enemies:
        return None
    tank = room.game.tanks.get(bot.slot, (0, 0))[0]
    gravity, w = aim.GRAVITY.get(tank, 98), wind(conn)
    bodies = [(x, y - aim.BODY // 2) for x, y in (place(room, bot, p.slot) for p in others)]
    friends = [me] + [place(room, bot, p.slot) for p in others if p not in enemies]
    kind = pick_kind(conn, tank, rng)
    cols = getattr(conn, 'weather', ())
    last = getattr(conn, 'last', None)
    target = next((p for p in enemies if last is not None and last[0] == p.slot and math.dist(last[1], me) <= REPEAT
                   and math.dist(last[2], place(room, bot, p.slot)) <= REPEAT), None)
    steady = target is not None
    if steady and last[3] == w:
        angle, power = last[4], last[5] * (1 + rng.choice((-1, 1)) * rng.uniform(0.01, 0.02))
        power = max(aim.POWER[0], min(aim.POWER[1], round(power)))
        hit = aim.fly(t, *me, angle, power, gravity, w, bodies, weather=cols)
    else:
        plans = {p.slot: aim.best_shot(t, me, place(room, bot, p.slot), gravity, w, bodies, friends[1:], cols)
                 for p in ([target] if steady else enemies)}
        target = target or min(enemies, key=lambda p: plans[p.slot][3]
                               + TIEBREAK * math.dist(me, place(room, bot, p.slot)))
        angle, power, hit, _ = plans[target.slot]
    tx, ty = place(room, bot, target.slot)
    crossed = set()
    aim.fly(t, *me, angle, power, gravity, w, bodies, weather=cols, crossed=crossed)
    situation = skill.ShotSituation(angle=angle if angle <= 90 else 180 - angle, distance=abs(tx - me[0]),
                                    max_distance=t.w, wind=w[0] / 26, ss=kind == 'ss',
                                    weather=bool(crossed & {'tornado', 'mirror'}))
    shot = profiles.shot(conn.layout, tank, kind)
    missed = False
    if not steady and rng.random() > skill.hit_chance(conn.n, situation, shot, skill.config(conn.server.config)):
        for _ in range(3):  # erra, mas não em cima de si mesmo nem de um aliado
            wrong = aim.miss(rng, power)
            miss = aim.fly(t, *me, angle, wrong, gravity, w, bodies, weather=cols)
            if miss is None or aim.safe(miss, (tx, ty), friends):
                power, hit, missed = wrong, miss, True
                break
    good = not missed and hit is not None and math.dist(hit, (tx, ty - aim.BODY // 2)) <= 2 * aim.BODY
    conn.last = (target.slot, me, (tx, ty), w, angle, power) if good else None
    return angle, power, hit or (max(0, min(t.w - 1, tx)), ty), kind  # saiu do mapa: a câmera mira o alvo (n >= 1 sempre)


def shot_body(x: int, y: int, angle: int, power: int, wind_: tuple[int, int], hit, v584: bool = False,
              shot2: bool = False) -> bytes:
    """0xc400 como o da captura: x, y, 01, tiro 2, ângulo, força, 01, 3x cano (bx, by), vento, 00, impactos.
    O 2º u8 (+0x1a4) é o tiro 2: quem recebe escolhe a animação fire2 e o projétil dele (0x4e09d0).
    v584 (tiros do admin): o 1º byte é o lado do tanque (+0xb0, o mesmo do 0x8402: 1 direita, 0 esquerda; com 1 e
    ângulo para a esquerda o tanque vira de costas para o tiro), força x5 e u16 + u8 a mais antes dos impactos."""
    bx, by = aim.muzzle(angle)
    impacts = [(8, *hit)] if hit else []
    face, extra = (int(angle <= 90), bytes(2)) if v584 else (1, b'')
    power = power * V584_POWER if v584 else power
    return (struct.pack('<HHBBhHB6hhhB', x, y, face, int(shot2), angle, power, 1, bx, by, bx, by, bx, by, *wind_, 0) + extra
            + bytes([len(impacts)]) + b''.join(struct.pack('<BHH', *i) for i in impacts))


async def shoot(room, bot, game, angle: int, power: int, hit, kind=1) -> None:
    x, y = place(room, bot, bot.slot)
    body = shot_body(x, y, angle, power, wind(bot.conn), hit, getattr(bot.conn, 'v584', False), kind == 2)
    # o 0x8006 leva os bytes 4/5 do 0xc400 trocados (todas as capturas); outro lado aqui viraria o tanque duas vezes
    await send(room, bot, AIM, struct.pack('<HHBB', x, y, body[5], body[4]))
    await asyncio.sleep(AIM_WAIT)
    if room.game is not game or not bot.alive:
        return
    craters(bot.conn, body)
    await send(room, bot, SS if kind == 'ss' else SHOT, body)
    later(room, bot, SHOT_WAIT, report(room, bot, 0x0e, game, SHOT_DELAY))


async def die(room, bot) -> None:
    """0xc304 (causa 1 inimigo, 2 aliado, 3 o próprio, como 0x47b156) + 0xc309, e o 0x4100 do lado do servidor."""
    from gunbound.game.protocol.game_play import announce_death
    killer = room.player_by_slot(bot.conn.last_hit)
    cause = 3 if killer in (None, bot) else 2 if killer.team == bot.team else 1
    body = struct.pack('<IB', cause | DIES_NOW, killer.slot if killer else bot.slot)
    await send(room, bot, DEATH, body)
    await send(room, bot, DEATH_ACK, bytes([bot.slot]) + body)
    await announce_death(room, bot, room.on_dead(bot.conn))


async def send(room, bot, kind: int, body: bytes) -> None:
    """Para os humanos (p2p_send) e, como se viesse pelo túnel, para os outros bots."""
    if room.game is None or room.players.get(bot.conn.id) is not bot:
        return
    await p2p_send(room, bot, kind, body.ljust(14, b'\x00'))
    for other in [p for p in room.players.values() if is_bot(p.conn) and p is not bot]:
        await react(room, other, bot, kind, body)


def later(room, bot, delay: float, coro) -> None:
    async def run():
        await asyncio.sleep(delay)
        await coro
    task = asyncio.create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
