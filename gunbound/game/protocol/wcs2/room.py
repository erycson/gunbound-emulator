"""
WCS2 (cliente v584): configuração da sala em um pacote só (0x3106 -> 0x3107) e itens da sala de espera (0x6050/0x6051/0x6052).
Endereços = GunBound.gme v584 (VA). Os outros pacotes do bloco ficam em events.py (0x3433), bonus.py (0x4300, 0x4520),
lobby.py (0x2025) e no room_join.py comum (0x2131/0x2132); o que falta está em docs/Cliente v584 - pacotes.md.
"""
from __future__ import annotations
from gunbound.base.enums import RoomMode, ROOM_SIZES, MAP_COUNT
from gunbound.game import room_packets as rp
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.enums import ServerPacket

CLI_ROOM_CHANGE_ALL = 0x3106     # envio 0x55dba5 (FUN_0055d8c0)
SRV_ROOM_CHANGE_ALL = 0x3107     # leitura ReadyMode 0x508820 (0x508de3)
CLI_READY_ITEMS_GET = 0x6050     # envio 0x507143 (GXPReadyMode, ao entrar na sala)
SRV_READY_ITEMS = 0x6051         # leitura global 0x40f740 (case 0x6051)
CLI_READY_ITEMS_SET = 0x6052     # envio 0x435e69 / 0x436796 (FUN_00435e50)

ITEM_ENTRY = 8  # u32 + u32 por posição

# shortcut: lista em memória do processo (some ao reiniciar); persistir exige tabela nova no banco (pendente).
_ready_items: dict[str, bytes] = {}


@handler(CLI_ROOM_CHANGE_ALL, master=True, waiting=True, register=False)
class RoomChangeAllRecv(GameRecv):
    """
    0x3106 (0x55dba5..0x55ddc9): u16 id-1 (1º u16 do registro escolhido na lista do diálogo, +0x68c7c), u8 +0x68cbc,
    u8 mapa (+0x68c9c % 17), u32 settings (mesmo formato do 0x3101/0x3103 do servidor), u8 capacidade (+0x68cb0 -> sala +0x10,
    a mesma que 0x3103 manda: 0x55a803..0x55a882). O cliente aplica na hora (0x55ddf2, evento local 0xC319) e no 0x3107 só
    olha o u16: 0 = nada, !=0 = popup de texto 0xC350E (0x508de3). Os dois primeiros campos não têm uso conhecido no servidor:
    são lidos e ignorados. Validação igual à dos 0x3101/0x3103/0x3104 (room_settings.py).
    """

    async def handle(self):
        buf = self.buf.require(9)
        buf.read_uint16(); buf.read_uint8()
        stage, settings, capacity = buf.read_uint8(), buf.read_uint32(), buf.read_uint8()
        room = self.room
        mode = RoomMode.parse(settings >> 16)
        ok = (stage < MAP_COUNT and mode is not None and capacity in ROOM_SIZES
              and all(p.slot < capacity for p in room.players.values()))
        if not ok:
            await self.conn.on_send(Packet.new(SRV_ROOM_CHANGE_ALL, rtc=1))
            return
        room.options.map, room.options.mode, room.options.settings = stage, mode, settings & 0xFFFF
        room.options.size = capacity
        for cmd, value in ((ServerPacket.SRV_LOBBY_ROOM_MAP, lambda p: p.u8(room.options.map)),
                           (ServerPacket.SRV_LOBBY_ROOM_SETTINGS, lambda p: p.u32(rp.settings_of(room))),
                           (ServerPacket.SRV_LOBBY_ROOM_MAXMEN, lambda p: p.u8(room.options.max_players()))):
            room.room_manager.notify_lobby(room, value(rp.lobby_room(cmd, room)))
        await self.conn.on_send(rp.ack(SRV_ROOM_CHANGE_ALL))
        await room.broadcast(rp.host_change(room), excepts=[self.conn.id])


@handler(CLI_READY_ITEMS_GET, register=False)  # sem room=True: o tutorial abre a sala de espera sem sala no servidor
class ReadyItemsGetRecv(GameRecv):
    """
    0x6050 sem corpo. Resposta 0x6051 (0x40f740): u16 rtc (só lê com 0), u16 n, n x [u32 nº do baú, u32 código do item]
    (0 = vazio; o cliente subtrai 0xAAA7A do código). Devolve o que o próprio cliente gravou pelo 0x6052.
    """

    async def handle(self):
        data = _ready_items.get(self.user_id(), b'\x00\x00')
        await self.conn.on_send(Packet.new(SRV_READY_ITEMS, rtc=0).raw(data))


@handler(CLI_READY_ITEMS_SET, register=False)
class ReadyItemsSetRecv(GameRecv):
    """0x6052 (FUN_00435e50): u16 n (+0x1b97c), n x [u32, u32] — o mesmo formato do 0x6051. Sem resposta no cliente."""

    async def handle(self):
        count = self.buf.require(2).read_uint16()
        count = min(count, self.buf.remaining() // ITEM_ENTRY)
        _ready_items[self.user_id()] = count.to_bytes(2, 'little') + self.buf.read_bytes(count * ITEM_ENTRY)
