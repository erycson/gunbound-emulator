"""
Comandos de GM, como no servidor original (GunBoundServ3.exe FUN_00425a10, via REA):
- Entrada: 0x5100 (SVC_COMMAND), texto cru (ex.: "/bcm -a oi"). Só para autoridade >= GM_AUTHORITY.
- Resposta: 0x5101 com o texto cru. O /bcm usa o mesmo 0x5101 para cada destinatário (FUN_0042faa0).
- Comandos do original: server, bcm, ban, disconnect, close, motd, room, version, limit, time, qsman, qsopt, toid.
- Extra deste servidor: /startgame (GM inicia a partida sozinho ou com times desbalanceados).
"""
from __future__ import annotations
import os
import random
import struct
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Awaitable, Callable
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import RoomMode
from gunbound.bot import room as bots
from gunbound.game import room_packets as rp
from gunbound.game.protocol.base import GameRecv, Packet, decrypt_blocks, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket
from gunbound.util.binary_buffer import PacketError
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection

GM_AUTHORITY = 99
MAX_COMMAND = 255
SYNTAX_ERROR = "ADMIN>> Syntax Error"
# comandos que o cliente já tratou e depois manda crus no 0x5100 (S2 0x42c532/0x42c404/0x42cb1b, cores 0x42cced):
# sem resposta, em vez de "Syntax Error"
CLIENT_ONLY = frozenset({"gg", "shrduatlwkr", "goto", "rjslskdlxm", "rjslemforhs", "ghkrudsla",
                         *(f"ehdzkffkvkdnj{i}" for i in range(1, 6))})
FOREVER = datetime(2099, 12, 31)
QUICK_MODES = {1: (RoomMode.SOLO, "Solo"), 2: (RoomMode.TAG, "Tag"), 3: (RoomMode.SCORE, "Score"), 4: (RoomMode.JEWEL, "Jewel")}


def is_gm(conn: 'ClientConnection') -> bool:
    return int(conn.data['profile'].get('Authority') or 0) >= GM_AUTHORITY


def text_packet(text: str) -> Packet:
    return Packet.new(ServerPacket.SRV_COMMAND).raw(text.encode('latin-1', errors='replace')[:MAX_COMMAND])


def logged_in(clients) -> list['ClientConnection']:
    return [c for c in list(clients.clients.values()) if 'profile' in c.data and not c.closing]


def find_by_nick(clients, nick: str) -> 'ClientConnection | None':
    nick = nick.lower()
    return next((c for c in logged_in(clients) if c.data['profile']['Nickname'].lower() == nick), None)


class GmCommands:
    """Um método por comando (`cmd_<nome>`); cada um devolve o texto da resposta (ou None se já respondeu)."""

    def __init__(self, conn: 'ClientConnection', rooms, clients, user_repository):
        self.conn, self.rooms, self.clients, self.users = conn, rooms, clients, user_repository

    @property
    def me(self) -> str:
        return self.conn.data['profile']['Nickname']

    async def run(self, text: str) -> str | None:
        name, _, arg = text[1:].partition(' ')
        if name.lower() in CLIENT_ONLY:
            return None
        method: Callable[[str], Awaitable[str | None]] | None = getattr(self, f"cmd_{name.lower()}", None)
        return await method(arg.strip()) if method else SYNTAX_ERROR

    async def cmd_server(self, arg):
        users = logged_in(self.clients)
        in_room = sum(1 for c in users if c.room is not None)
        in_channel = sum(1 for c in users if c.channel is not None)
        return (f"- Connection : {self.clients.size()}\n- User count : {len(users)}\n- Room count : {self.rooms.size()}\n"
                f"- User count in room : {in_room}\n- User count in channel : {in_channel}")

    async def cmd_bcm(self, arg):
        """/bcm [-a|-c|-r] msg: todos (padrão), só o canal ou só a sala de quem mandou."""
        scope, msg = 'a', arg
        if arg.startswith('-') and len(arg) >= 2:
            scope, msg = arg[1], arg[2:].strip()
        if scope not in 'acr' or not msg:
            return SYNTAX_ERROR
        targets = logged_in(self.clients)
        if scope == 'c':
            targets = [c for c in targets if c.channel is not None and c.channel is self.conn.channel]
        elif scope == 'r':
            targets = [c for c in targets if c.room is not None and c.room is self.conn.room]
        for c in targets:
            await c.on_send(text_packet(msg))
        return f"ADMIN>> Message broadcasted successfully from '{self.me}' to {len(targets)}: {msg}"

    async def cmd_ban(self, arg):
        """/ban -e|-dN|-hN usuario [motivo]: grava RestrictTime e derruba a sessão."""
        parts = arg.split(None, 2)
        if len(parts) < 2 or not parts[0].startswith('-'):
            return SYNTAX_ERROR
        flag, user_id = parts[0][1:], parts[1]
        if flag == 'e':
            until, label = FOREVER, None
        elif flag[:1] in ('d', 'h') and flag[1:].isdigit() and int(flag[1:]) > 0:
            hours = int(flag[1:]) * (24 if flag[0] == 'd' else 1)
            until, label = datetime.now() + timedelta(hours=hours), hours
        else:
            return SYNTAX_ERROR
        if not await self.users.set_restrict_time(user_id, until):
            return f"ADMIN>> Failed to update User database while banning '{user_id}'"
        target = next((c for c in logged_in(self.clients) if c.data['profile']['Id'] == user_id), None)
        if target is not None:
            await target.close()
        if label is None:
            return f"ADMIN>> User '{user_id}' is successfully banned forever by '{self.me}'"
        return f"ADMIN>> User '{user_id}' is successfully banned for {label} hours by '{self.me}'"

    async def cmd_disconnect(self, arg):
        if not arg:
            return SYNTAX_ERROR
        target = find_by_nick(self.clients, arg)
        if target is None:
            return "ADMIN>> failed to kick thru gunbound database"
        await target.close()
        return f"ADMIN>> user '{arg}' is about to be disconnected by '{self.me}'"

    async def cmd_silence(self, arg):
        return await self.cmd_mute(arg)

    async def cmd_mute(self, arg):
        """/silence (ou /mute, que o TH e o S2 tratam sozinhos como ignorar) apelido segundos: 0x1040 u32 segundos (0 tira). O cliente bloqueia o chat e mostra o tempo (texto 516).
        Não existe no servidor original (nenhum gatilho para o 0x1040); o bloqueio é só no cliente."""
        nick, _, secs = arg.partition(' ')
        target = find_by_nick(self.clients, nick) if secs.strip().isdigit() else None
        if target is None:
            return SYNTAX_ERROR if not secs.strip().isdigit() else f"ADMIN>> user '{nick}' is not online"
        await target.on_send(Packet.new(ServerPacket.SRV_CHAT_MUTE).u32(int(secs)))
        return f"ADMIN>> user '{nick}' is muted for {int(secs)} seconds by '{self.me}'"

    async def cmd_close(self, arg):
        room = self.rooms.get(int(arg)) if arg.isdigit() else None
        if room is None:
            return "ADMIN>> Room number is invalid"
        for p in list(room.players.values()):
            await p.conn.on_send(Packet.new(ServerPacket.SRV_ROOM_KICKED))
            await self.rooms.leave(p.conn)
        return f"ADMIN>> Room {arg} is successfully broken by {self.me}"

    async def cmd_motd(self, arg):
        """/motd -c msg (canal) | -r msg (sala). Vale até reiniciar o servidor."""
        if len(arg) < 3 or arg[0] != '-' or arg[1] not in 'cr':
            return SYNTAX_ERROR
        msg = arg[2:].strip()
        if arg[1] == 'c':
            self.conn.server.config['announcement'] = msg
            return f"ADMIN>> Channel motd is changed successfully by {self.me}"
        self.rooms.room_motd = msg
        return f"ADMIN>> Room motd is changed successfully by {self.me}"

    async def cmd_room(self, arg):
        room = self.rooms.get(int(arg)) if arg.isdigit() else None
        if room is None:
            return "ADMIN>> Room not found"
        names = ', '.join(p.conn.data['profile']['Nickname'] for p in room.sorted_players())
        state = "esperando" if room.is_waiting() else "em jogo"
        return f"Sala {room.id} '{room.options.name}' {room.options.mode.name} {room.player_count()}/{room.options.max_players()} {state}: {names}"

    async def cmd_version(self, arg):
        cfg = self.conn.server.config
        return f"- First valid version : {cfg['version_min']}\n- Last valid version  : {cfg['version_max']}"

    async def cmd_limit(self, arg):
        cfg = self.conn.server.config
        return f"- Grade restrict : {cfg.get('grade_min', -4)} -> {cfg.get('grade_max', 19)}"

    async def cmd_time(self, arg):
        return datetime.now().strftime("ADMIN>> Server time is %c")

    async def cmd_qsman(self, arg):
        old = self.rooms.quick_min_players
        if arg.isdigit() and int(arg) < 8:  # original: só aceita < 8
            self.rooms.quick_min_players = int(arg)
        return f"- Current Quick Start Man : {old}\n- New Quick Start Man  : {self.rooms.quick_min_players}"

    async def cmd_qsopt(self, arg):
        mode = QUICK_MODES.get(int(arg)) if arg.isdigit() else None
        if mode is None:
            return SYNTAX_ERROR
        self.rooms.quick_mode = mode[0]
        return f"Change QuickStart {mode[1]} Mode"

    async def cmd_toid(self, arg):
        target = find_by_nick(self.clients, arg) if arg else None
        if target is None:
            return "ADMIN>> Failed to query matching user"
        return f"ID: {target.data['profile']['Id']} NICKNAME: {target.data['profile']['Nickname']}"

    async def cmd_startgame(self, arg):
        """Extra: o GM mestre da sala inicia sem as regras de prontos/times (jogo solo de GM/Adm)."""
        room = self.conn.room
        if room is None or not room.is_master(self.conn) or not room.is_waiting():
            return "ADMIN>> Você precisa ser o mestre de uma sala aguardando."
        await start_game(room, self.conn, start_echo(room.options.settings))
        return None


def start_echo(settings: int, rng=random) -> bytes:
    """Corpo do 0x3430 como o cliente v584 monta (0x433770): seed u32 (GetTickCount); sem ele o S2 lê a 0x3432 curta
    e fecha. Modo interno = bits 18-20 do settings (0x50f167). Modo 3 (Jewel): 6 x (u16 rand, u8 rand % 3);
    modo 4: 3 x (u16 rand, u8 de 1/2/4/8/16)."""
    out = bytearray(os.urandom(4))
    mode = settings >> 18 & 7
    if mode == 3:
        for _ in range(6):
            out += struct.pack('<HB', rng.randrange(0x8000), rng.randrange(3))
    elif mode == 4:
        for _ in range(3):
            out += struct.pack('<HB', rng.randrange(0x8000), rng.choice((1, 2, 4, 8, 16)))
    return bytes(out)


async def start_game(room, master: 'ClientConnection', echo: bytes) -> None:
    """Início comum ao 0x3430 e ao /startgame: só 0x3432 (cifrado) para a sala; no original o 0x3431 é apenas erro."""
    from gunbound.game.protocol.wcs2.bonus import roll_bonus
    room.start()
    room.game.bonus_event = roll_bonus(master.server.config)
    print(f"[sala {room.id}] início: mapa {room.game.map}, settings {room.options.settings:08X}, "
          f"spawns {room.game.spawns}, tanques {room.game.tanks}, ordem {room.game.turn_order}")
    body = rp.game_start_body(room, echo)
    print(f"[sala {room.id}] 0x3432 em claro: {body.hex(' ').upper()}")
    await room.broadcast(rp.game_start(body))


@handler(ClientPacket.CLI_COMMAND)
class CommandRecv(GameRecv):
    """0x5100 SVC_COMMAND: texto cru do comando. Não-GM é ignorado, como no original (checa autoridade antes)."""

    @inject
    async def handle(self, rooms=Provide['rooms'], clients=Provide['clients'], user_repository=Provide['user_repository'],
                     inventory_repository=Provide['inventory_repository']):
        self.conn.last_activity = time.time()
        text = self.buf.read_bytes().split(b'\x00', 1)[0].decode('latin-1').strip()[:MAX_COMMAND]
        if text.lower().split(' ', 1)[0] == '/bot' and bots.enabled(self.conn):  # bot: para todos (gunbound/bot)
            await self.conn.on_send(text_packet(await bots.command(self.conn, text, inventory_repository)))
            return
        if not text.startswith('/') or not is_gm(self.conn):
            return
        print(f"[{self.conn.addr}] GM {self.conn.data['profile']['Id']}: {text}")
        msg = await GmCommands(self.conn, rooms, clients, user_repository).run(text)
        if msg:
            await self.conn.on_send(text_packet(msg))


@handler(ClientPacket.CLI_BCM)
class BcmRecv(GameRecv):
    """0x5010 SVC_BCM (16..272 bytes, cifrado como o chat): mensagem para todos em 0x5101. Só GM."""

    @inject
    async def handle(self, clients=Provide['clients']):
        if not is_gm(self.conn):
            return
        try:
            body = decrypt_blocks(self.conn, self.buf.read_bytes(), self.command)
        except PacketError as e:
            print(f"[{self.conn.addr}] 0x5010 inválido: {e}")
            return
        size = body.read_uint8()
        msg = body.read_string(min(size, body.remaining()), encoding='latin-1')
        for c in logged_in(clients):
            await c.on_send(text_packet(msg))
