"""
Serializadores dos pacotes de sala (S->C), um lugar só para os layouts de docs/Protocolo-Salas.md (F3, [TH×2]).
Os handlers só decidem *quando* enviar; o *formato* fica aqui.
"""
from __future__ import annotations
import socket
from gunbound.util.local_udp import real_udp_port
from typing import TYPE_CHECKING, Iterable
from gunbound.base.enums import RoomStatus
from gunbound.game.protocol.base import Packet, EncryptedPacket
from gunbound.game.protocol.enums import ServerPacket
from gunbound.game import phase
if TYPE_CHECKING:
    from gunbound.game.room import Room, RoomPlayer
    from gunbound.game.client import ClientConnection

DEFAULT_UDP_PORT = 8363     # F2; o cliente informa a porta real no login (bloco 3), que tem preferência
# Desligado: com a porta real o P2P UDP não se estabelece (ping fica 250ms e o mestre ignora o "pronto"); com a porta errada cai no túnel TCP e funciona
LOCAL_UDP_FIX = False


def settings_of(room: 'Room') -> int:
    """settings u32 cru da sala (0x2103, 0x2105, 0x21F4, 0x3432)."""
    return room.options.settings


def player_net(conn: 'ClientConnection') -> tuple[bytes, int]:
    """IP (ordem de rede) e porta UDP do jogador. Usa o informado no login; senão, o IP do socket."""
    net = conn.data.get('net')
    if net and net[0]:
        if LOCAL_UDP_FIX and int(net[0]) == 0x0100007F:  # 127.0.0.1: dois clientes no mesmo PC, a porta informada pode estar errada
            conn.data['local_udp'] = conn.data.get('local_udp') or real_udp_port(int(conn.addr.rsplit(':', 1)[1]))
        return int(net[0]).to_bytes(4, 'little'), conn.data.get('local_udp') or int(net[1]) or DEFAULT_UDP_PORT
    ip = conn.addr.rsplit(':', 1)[0]
    try:
        return socket.inet_aton(ip), DEFAULT_UDP_PORT
    except OSError:
        return b'\x00' * 4, DEFAULT_UDP_PORT


def write_room_header(pkt: Packet, room: 'Room') -> Packet:
    return pkt.pstr(room.options.name).u8(room.options.map).u32(settings_of(room))


def write_player(pkt: Packet, p: 'RoomPlayer', with_flag: bool = True) -> Packet:
    conn = p.conn
    profile, game = conn.data['profile'], conn.data['game']
    ip, port = player_net(conn)
    pkt.u8(p.slot).fixed(profile['Nickname'], 12).u8(profile.get('Gender') or 0)
    pkt.raw(ip).u16be(port).raw(ip).u16be(port)
    pkt.u8(p.tank1).u8(p.tank2).u8(p.team)
    if with_flag:  # 0x2111: estado do slot (cliente 0x4cbb9e, +0x24342). 0 some com o jogador; 1 = presente, 3 = pronto (0x4ecbd9)
        pkt.u8(3 if getattr(p, 'ready', False) else 1)
    pkt.fixed(game.get('Guild') or '', 8).raw(phase.of(conn).grades(game))  # patentes antes dos itens, como no 0x200E
    phase.of(conn).write_avatar(pkt, conn.data.get('avatar') or [], conn.data.get('avatar_enchant'))
    return pkt.raw(phase.of(conn).player_tail(is_power_user(conn)))


def is_power_user(conn: 'ClientConnection') -> bool:
    return bool(conn.data.get('power_user'))  # definido ao carregar o baú (protocol/item.py)


# ---------- lobby ----------
def room_list(rooms: Iterable['Room']) -> Packet:
    rooms = list(rooms)
    pkt = Packet.new(ServerPacket.SRV_ROOM_SORTED_LIST, rtc=0).u16(len(rooms))
    for r in rooms:
        write_list_entry(pkt, r, in_list=True)
    return pkt.u8(0)


def room_list_by_id(entries) -> Packet:
    """0x2103 do 0x2101: (id, sala ou None) na ordem pedida; sala inexistente ou automática = u16 id + u8 0 (título vazio)."""
    pkt = Packet.new(ServerPacket.SRV_ROOM_SORTED_LIST, rtc=0).u16(len(entries))
    for room_id, r in entries:
        if r is None or getattr(r, 'auto', False):
            pkt.u16(room_id).u8(0)
        else:
            write_list_entry(pkt, r, in_list=True)
    return pkt.u8(0)


def write_list_entry(pkt: Packet, r: 'Room', in_list: bool = False) -> Packet:
    pkt.u16(r.id)
    write_room_header(pkt, r)
    pkt.u8(1 if is_power_user(r.owner) else 0)
    if in_list:  # só o 0x2103 (o 0x21F0 não tem): o v440 manda um byte a mais, o TH nenhum
        pkt.raw(phase.of(r.owner).list_entry_extra())
    pkt.u8(r.player_count()).u8(r.options.max_players())
    pkt.u8(0 if r.is_waiting() else 1).u8(1 if r.options.is_protected() else 0)
    if in_list and r.options.stage is not None:  # 0x2103 no canal Stage (v584 0x4d5ebf): u16 StageNum-1, u8 GameMode
        pkt.u16(r.options.stage[0]).u8(r.options.stage[1])
    return pkt


def lobby_room_created(room: 'Room') -> Packet:
    return write_list_entry(Packet.new(ServerPacket.SRV_LOBBY_ROOM_CREATED), room)


def lobby_room(cmd: int, room: 'Room') -> Packet:
    """0x21F1..0x21F7: u16 id; o chamador acrescenta o campo alterado."""
    return Packet.new(cmd).u16(room.id)


def room_detail(room: 'Room') -> Packet:
    pkt = Packet.new(ServerPacket.SRV_ROOM_DETAIL, rtc=0)
    write_room_header(pkt, room)
    pkt.u8(1 if is_power_user(room.owner) else 0)
    pkt.u8(room.player_count()).u8(room.options.max_players())
    pkt.u8(0 if room.is_waiting() else 1).u8(1 if room.options.is_protected() else 0)
    for p in room.sorted_players():
        phase.of(room.owner).write_detail_player(pkt, p)
    return pkt


def room_error(cmd: int, code: int) -> Packet:
    """Erro de sala: só o u16 de código (F3: 0x0011 inexistente/senha, 0x2001 cheia)."""
    return Packet.new(cmd, rtc=code)


# ---------- entrar / sair ----------


def join_state(room: 'Room', me: 'RoomPlayer', motd: str, cmd: int = ServerPacket.SRV_ROOM_JOIN) -> Packet:
    """0x2111 (entrar) e 0x2133 (quick start) usam o mesmo corpo no servidor original (0x414436/0x414446)."""
    pkt = Packet.new(cmd, rtc=0).u8(room.master_slot()).u8(me.slot).u16(room.id)
    write_room_header(pkt, room)
    pkt.raw(room.options.item_bytes)
    pkt.u8(room.options.max_players()).u8(room.player_count())
    for p in room.sorted_players():
        write_player(pkt, p)
    return pkt.text(motd)


def quick_created(room: 'Room', motd: str) -> Packet:
    """0x2132 (original 0x413e68): u8 slot, u16 sala, [v584: u8], u8 máx, pstr título, u8 mapa, u32 settings, MOTD.
    O cliente (v440 0x4cc1c8) vira mestre da sala de espera."""
    pkt = Packet.new(ServerPacket.SRV_ROOM_QUICK_CREATE, rtc=0).u8(room.master_slot()).u16(room.id)
    pkt.raw(phase.of(room.owner).quick_create_extra).u8(room.options.max_players())
    return pkt.pstr(room.options.name).u8(room.options.map).u32(settings_of(room)).text(motd)


def player_joined(p: 'RoomPlayer') -> Packet:
    return write_player(Packet.new(ServerPacket.SRV_ROOM_PLAYER_JOIN), p, with_flag=False)


def player_left(slot: int) -> Packet:
    return Packet.new(ServerPacket.SRV_ROOM_PLAYER_LEAVE).u16(slot)


def host_change(room: 'Room') -> Packet:
    pkt = Packet.new(ServerPacket.SRV_ROOM_HOST_CHANGE).u8(room.master_slot())
    write_room_header(pkt, room)
    return pkt.raw(room.options.item_bytes).u8(room.options.max_players())


def ack(cmd: int) -> Packet:
    """Confirmação simples: só RTC = 0."""
    return Packet.new(cmd, rtc=0)


# ---------- partida ----------
def game_start(room: 'Room', echo: bytes) -> EncryptedPacket:
    """0x3432 (cifrado): settings, mapa em jogo, jogadores (22 bytes cada), marcador de evento e eco do 0x3430."""
    from gunbound.util.binary_buffer import BinaryWriter
    w = BinaryWriter()
    w.write_uint32(settings_of(room))
    w.write_uint8(room.game.map)
    players = room.sorted_players()
    w.write_uint16(len(players))
    for p in players:
        x, y = room.game.spawn_of(p.slot)
        w.write_uint8(p.slot)
        w.write_string(p.conn.data['profile']['Nickname'], 12)
        w.write_uint8(p.team)
        w.write_uint8(room.game.tank1_of(p))
        w.write_uint8(room.game.tank2_of(p))
        w.write_uint16(x)
        w.write_uint16(y)
        w.write_uint16(room.game.turn_order.index(p.slot))
    w.write_bytes(phase.of(room.owner).game_start_tail(echo, room.game.bonus_event))
    return EncryptedPacket.build(ServerPacket.SRV_START_GAME, w.getvalue())


def player_dead(slot: int, team: int) -> EncryptedPacket:
    return EncryptedPacket.build(ServerPacket.SRV_GAME_DEAD, bytes([slot]) + bytes.fromhex('13000000000000443447') + bytes([team]))


def winner(team: int) -> EncryptedPacket:
    return EncryptedPacket.build(ServerPacket.SRV_GAME_WINNER, bytes([team]) + b'\x00' * 11)


def tunnel(origin_slot: int, data: bytes) -> Packet:
    return Packet.new(ServerPacket.SRV_GAME_TUNNEL).u8(origin_slot).raw(data)


def status_byte(room: 'Room') -> int:
    return 0 if room.status == RoomStatus.WAITING else 1
