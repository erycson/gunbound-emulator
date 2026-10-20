"""
Console de administração do servidor original (GunBoundServ3.exe, via REA; ver docs/Opcodes do servidor original.md).
- 0x1011 SVC_LOGIN/ADMIN: login normal marcando a sessão como console (fica em login.py).
- 0x2020/0x2022 SVC_CHANNEL_MONITOR(_STOP): GM >= 98 passa a receber o chat de todos os canais.
- 0x5110..0x512C SVC_CMD_*: corpo em claro, resposta = opcode + 1 com RTC (0 ok). STATUS/MOTD/BCM exigem
  autoridade >= 98 (0x427470); os demais >= 99 (0x427490). Sem permissão o original não responde.
Os valores alterados ficam em memória (o original também grava no setting.txt; aqui valem até reiniciar).
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.game.protocol.gm_commands import logged_in, text_packet
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection

MONITOR_AUTHORITY = 98      # 0x427470: [conn+0x9c8] >= 0x62
ADMIN_AUTHORITY = 99        # 0x427490: [conn+0x9c8] >= 0x63
EVENT_SLOTS = 4             # SET_EVENTACTPROB: índice < 4, liga o bit 0x100000 << índice do FUNCTION_RESTRICT
EVENT_FLAG = 0x100000
MAX_ALLOWED_GUILD = 0x4F

# Chat de todos os canais vai também para estes (SVC_CHANNEL_MONITOR)
monitors: set['ClientConnection'] = set()


def authority(conn: 'ClientConnection') -> int:
    return int(conn.data['profile'].get('Authority') or 0)


class AdminState:
    """Valores ajustáveis pelo console, guardados na config do GameServer (mesmas chaves do config.yml)."""

    def __init__(self, config):
        self.config = config
        config.setdefault('guild_limit', 0)
        config.setdefault('function_restrict', 0)
        config.setdefault('passable_auth', 0)
        config.setdefault('allowed_guild', '')
        config.setdefault('events', [(0, 0, 0)] * EVENT_SLOTS)

    def status(self, clients, rooms) -> Packet:
        """0x5111, layout do original (0x42a1ad..0x42a4e3)."""
        cfg = self.config
        users = logged_in(clients)
        pkt = (Packet.new(ServerPacket.SRV_CMD_STATUS, rtc=0)
               .u16(len(users)).u16(rooms.size()).u16(sum(1 for c in users if c.room is not None))
               .u16(sum(1 for c in users if c.channel is not None))
               .u16(cfg['grade_min'] & 0xFFFF).u16(cfg['grade_max'] & 0xFFFF).u16(cfg['guild_limit'] & 0xFFFF)
               .u8(1 if cfg['allowed_guild'] else 0).u32(cfg['function_restrict']).u8(0)
               .u32(cfg['version_min']).u32(cfg['version_max']))
        active = [(i, e) for i, e in enumerate(cfg['events']) if cfg['function_restrict'] & (EVENT_FLAG << i)]
        pkt.u16(len(active))
        for i, (prob, a, b) in active:
            pkt.u16(i).u16(prob).u8(a).u8(b)
        return pkt.u16(cfg['passable_auth'] & 0xFFFF).u32(cfg['score_factor']).u32(cfg['gold_factor'])


def admin_command(cmd: int, level: int = ADMIN_AUTHORITY):
    """Registra um SVC_CMD_*: sem autoridade não responde; o handler devolve o RTC da resposta (opcode + 1)."""
    def wrap(fn):
        @handler(cmd)
        class _Recv(GameRecv):
            @inject
            async def handle(self, clients=Provide['clients'], rooms=Provide['rooms']):
                if authority(self.conn) < level:
                    print(f"[{self.conn.addr}] 0x{cmd:04X} sem autoridade")
                    return
                state = AdminState(self.conn.server.config)
                result = await fn(self, state, clients, rooms)
                if isinstance(result, Packet):
                    await self.conn.on_send(result)
                elif result is not None:
                    await self.conn.on_send(Packet.new(cmd + 1, rtc=result))
        _Recv.__name__ = f"{fn.__name__}Recv"
        return _Recv
    return wrap


@admin_command(ClientPacket.CLI_CMD_STATUS, MONITOR_AUTHORITY)
async def CmdStatus(self, state, clients, rooms):
    return state.status(clients, rooms)


@admin_command(ClientPacket.CLI_CMD_MOTD, MONITOR_AUTHORITY)
async def CmdMotd(self, state, clients, rooms):
    """u8 alvo (1 = canal, 2 = sala) + texto."""
    target = self.buf.read_uint8()
    text = self.buf.read_bytes().split(b'\x00', 1)[0].decode('latin-1')
    if target == 1:
        state.config['announcement'] = text
    elif target == 2:
        rooms.room_motd = text
    else:
        return ServerCode.SRV_DENIED
    return ServerCode.SRV_OK


@admin_command(ClientPacket.CLI_CMD_BCM, MONITOR_AUTHORITY)
async def CmdBcm(self, state, clients, rooms):
    """u8 ignorado + texto, repassado a todos em 0x5101 (0x42faa0)."""
    self.buf.read_uint8()
    msg = self.buf.read_bytes().split(b'\x00', 1)[0].decode('latin-1')
    for c in logged_in(clients):
        await c.on_send(text_packet(msg))
    return ServerCode.SRV_OK


@admin_command(ClientPacket.CLI_CMD_SETVERSION)
async def CmdSetVersion(self, state, clients, rooms):
    """u32 mínima + u32 máxima. Se a faixa estreitar, o original derruba quem ficou fora (0x40a530) e não responde."""
    vmin, vmax = self.buf.read_uint32(), self.buf.read_uint32()
    narrowed = vmin > state.config['version_min'] or vmax < state.config['version_max']
    state.config['version_min'], state.config['version_max'] = vmin, vmax
    if narrowed:
        print(f"[{self.conn.addr}] SETVERSION estreitou a faixa para {vmin}..{vmax} (sessões abertas não são verificadas)")
        return None
    return ServerCode.SRV_OK


@admin_command(ClientPacket.CLI_CMD_GRADELIMIT)
async def CmdGradeLimit(self, state, clients, rooms):
    state.config['grade_min'], state.config['grade_max'] = self.buf.read_int16(), self.buf.read_int16()
    return ServerCode.SRV_OK


@admin_command(ClientPacket.CLI_CMD_GUILDLIMIT)
async def CmdGuildLimit(self, state, clients, rooms):
    state.config['guild_limit'] = self.buf.read_uint16()
    return ServerCode.SRV_OK


@admin_command(ClientPacket.CLI_CMD_FUNCTION_RESTRICT)
async def CmdFunctionRestrict(self, state, clients, rooms):
    """u32 máscara + u32 valor: só os bits da máscara mudam."""
    mask, value = self.buf.read_uint32(), self.buf.read_uint32()
    state.config['function_restrict'] = (value & mask) | (state.config['function_restrict'] & ~mask & 0xFFFFFFFF)
    return ServerCode.SRV_OK


@admin_command(ClientPacket.CLI_CMD_SET_ALLOWEDGUILD)
async def CmdSetAllowedGuild(self, state, clients, rooms):
    size = self.buf.read_uint16()
    if size > MAX_ALLOWED_GUILD:
        return ServerCode.SRV_INVALID_ARG
    state.config['allowed_guild'] = self.buf.read_bytes(size).split(b'\x00', 1)[0].decode('latin-1')
    return ServerCode.SRV_OK


@admin_command(ClientPacket.CLI_CMD_SET_EVENTACTPROB)
async def CmdSetEventActProb(self, state, clients, rooms):
    """u16 índice (< 4) + u16 probabilidade + u8 + u8. Probabilidade 0 desliga o evento."""
    index, prob, a, b = self.buf.read_uint16(), self.buf.read_uint16(), self.buf.read_uint8(), self.buf.read_uint8()
    if index >= EVENT_SLOTS:
        return None
    events = list(state.config['events'])
    events[index] = (prob, a, b)
    state.config['events'] = events
    flag = EVENT_FLAG << index
    state.config['function_restrict'] = state.config['function_restrict'] | flag if prob else state.config['function_restrict'] & ~flag
    return ServerCode.SRV_OK


@admin_command(ClientPacket.CLI_CMD_SET_PASSABLE_AUTH)
async def CmdSetPassableAuth(self, state, clients, rooms):
    state.config['passable_auth'] = self.buf.read_int16()
    return ServerCode.SRV_OK


@admin_command(ClientPacket.CLI_CMD_SET_FACTOR)
async def CmdSetFactor(self, state, clients, rooms):
    """u32 ScoreFactor + u32 GoldFactor (globais 0x4969e0/0x4969e4). Vale para os próximos logins e tetos de resultado."""
    state.config['score_factor'], state.config['gold_factor'] = self.buf.read_uint32(), self.buf.read_uint32()
    return ServerCode.SRV_OK


@handler(ClientPacket.CLI_CHANNEL_MONITOR)
class ChannelMonitorRecv(GameRecv):
    async def handle(self):
        if authority(self.conn) < MONITOR_AUTHORITY:
            await self.conn.on_send(Packet.new(ServerPacket.SRV_CHANNEL_MONITOR, rtc=ServerCode.SRV_DENIED))
            return
        monitors.add(self.conn)
        await self.conn.on_send(Packet.new(ServerPacket.SRV_CHANNEL_MONITOR, rtc=0))


@handler(ClientPacket.CLI_CHANNEL_MONITOR_STOP)
class ChannelMonitorStopRecv(GameRecv):
    async def handle(self):
        if authority(self.conn) < MONITOR_AUTHORITY:
            return
        monitors.discard(self.conn)
        await self.conn.on_send(Packet.new(ServerPacket.SRV_CHANNEL_MONITOR_STOP, rtc=0))


async def forward_to_monitors(sender: 'ClientConnection', make_packet) -> None:
    """Chat de canal para os monitores de outros canais. Um pacote novo por destino: o chat é cifrado no próprio buffer."""
    for m in list(monitors):
        if m.closing:
            monitors.discard(m)
        elif m.channel is not sender.channel:
            await m.on_send(make_packet())
