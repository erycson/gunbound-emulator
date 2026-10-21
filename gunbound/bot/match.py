"""
Bot na partida (docs/Bots.md, estágios 1a e 1b): responde o ciclo de turno do P2P como um cliente, passa a vez no turno
dele (1a) e morre quando o mestre manda (1b). Ainda não atira. Regras da captura v584 1x1
(tests/fixtures/bot_turn_replay.txt) e do cliente:
o mestre (0x42e798) só espera um 0xc302 de cada slot por fase (0f início/passe, 0e tiro, 02 pronto) e não lê o
contador; 0xc40a e 0xc309 caem no default do despachante (0x4dd8a0), vão só para imitar.
Morte: cada cliente calcula o HP de todos os tanques. Na escolha do próximo turno (0x4f5aa0) o mestre manda 0xc312
(u8 slot) para quem tem HP <= 0 ou y >= 9000 e não se declarou; o cliente responde 0xc314 (vazio); o mestre confere o
tanque de quem respondeu e manda 0xc315 (u8 slot); o dono manda 0xc304 (u32 causa, u8 matador) e o TCP 0x4100
(0x4e0596). Então o servidor não calcula dano: o bot segue esse caminho.
"""
from __future__ import annotations
import asyncio
import struct
from Crypto.Cipher import AES
from gunbound.bot.room import is_bot, p2p_key, p2p_send

START, NEXT, PASS, REPORT, SYNC, DEATH, POS, DEATH_ACK = 0x8600, 0xC300, 0xC301, 0xC302, 0xC303, 0xC304, 0xC40A, 0xC309
CHECK, CHECK_ACK, KILL = 0xC312, 0xC314, 0xC315
SHOTS = (0xC400, 0xC409)
PASS_DELAY = 9000   # u16 do C301, soma no delay do slot (0x41c3b0); 0xffff/0xea60 não somam e o bot ganharia todo turno
SHOT_WAIT = 3.0     # humanos mandam o 0e 1,3..3,3 s depois do tiro; atrasado é seguro, o mestre só espera
TURN_WAIT = 3.0     # o bot "pensa" antes de passar
_tasks: set[asyncio.Task] = set()


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
    if kind == START and from_master:
        await report(room, bot, 0x0f)
    elif kind in SHOTS:
        conn.last_hit = sender.slot  # o cliente guarda quem acertou por último (+0x2a4); aqui, quem atirou por último
        later(room, bot, SHOT_WAIT, report(room, bot, 0x0e, game))
    elif kind == PASS:
        await report(room, bot, 0x0f)
    elif kind == NEXT and from_master and len(body) >= 3:
        conn.whose, conn.counter, conn.tail = body[0], struct.unpack_from('<H', body, 1)[0] + 1, body[3:]
        await report(room, bot, 0x02)
    elif kind == SYNC and from_master and body[:1] == b'\x02' and conn.whose == bot.slot:
        conn.whose = -1
        later(room, bot, TURN_WAIT, pass_turn(room, bot, game))
    elif kind == CHECK and from_master and body[:1] == bytes([bot.slot]) and bot.alive:
        await send(room, bot, CHECK_ACK, b'')
    elif kind == KILL and from_master and body[:1] == bytes([bot.slot]) and bot.alive:
        await die(room, bot)
    elif kind == DEATH and len(body) >= 5:
        await send(room, bot, DEATH_ACK, bytes([sender.slot]) + body[:5])


async def report(room, bot, phase: int, game=None) -> None:
    """C40A (posição) + C302 (fase, u32 contador). 0e: u32 delay em +5, só lido do atirador."""
    if room.game is None or (game is not None and room.game is not game):
        return
    x, y = room.game.spawns.get(bot.slot, (0, 0))
    await send(room, bot, POS, struct.pack('<II', x, y))
    await send(room, bot, REPORT, struct.pack('<BI', phase, bot.conn.counter))


async def pass_turn(room, bot, game) -> None:
    """C301 = 01 + u16 delay + estado do próximo turno (o cliente copia 0x60 bytes; o mestre ecoa no C300)."""
    if room.game is not game:
        return
    await send(room, bot, PASS, b'\x01' + struct.pack('<H', PASS_DELAY) + bot.conn.tail)
    await report(room, bot, 0x0f)


async def die(room, bot) -> None:
    """0xc304 (causa 1 inimigo, 2 aliado, 3 o próprio, como 0x47b156) + 0xc309, e o 0x4100 do lado do servidor."""
    from gunbound.game.protocol.game_play import announce_death
    killer = room.player_by_slot(bot.conn.last_hit)
    cause = 3 if killer in (None, bot) else 2 if killer.team == bot.team else 1
    body = struct.pack('<IB', cause, killer.slot if killer else bot.slot)
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
