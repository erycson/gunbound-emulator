"""Configuração da sala pelo mestre (0x3100..0x3104), time (0x3210), pronto (0x3230) e expulsão (0x3150)."""
from __future__ import annotations
from gunbound.base.enums import RoomMode, RoomOptions, ROOM_SIZES, MAP_COUNT
from gunbound.game import room_packets as rp, phase
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket


class RoomChangeBase(GameRecv):
    """Só o mestre e só com a sala aguardando (guardas). `apply()` valida e altera; 0x3105 para o mestre, 0x3400 para os outros."""

    def apply(self) -> bool:
        raise NotImplementedError

    def lobby(self):
        """Pacote 0x21F2..0x21F6 para a lista de salas do lobby, ou None."""
        return None

    async def handle(self):
        if self.apply():
            packet = self.lobby()
            if packet is not None:
                self.room.room_manager.notify_lobby(self.room, packet)
            # o cliente trata o 0x3105 como confirmação da própria mudança (0x4ec6e9 aplica o que ele tem na tela);
            # os outros recebem o cabeçalho novo pelo 0x3400, que relê título, mapa, settings, itens e capacidade (0x4ecb20)
            await self.conn.on_send(rp.ack(ServerPacket.SRV_ROOM_UPDATE))
            await self.room.broadcast(rp.host_change(self.room), excepts=[self.conn.id])


@handler(ClientPacket.CLI_ROOM_CHANGE_STAGE, master=True, waiting=True)
class RoomChangeStageRecv(RoomChangeBase):
    def apply(self) -> bool:
        stage = self.buf.require(1).read_uint8()
        if stage >= MAP_COUNT:
            return False
        self.room.options.map = stage
        return True

    def lobby(self):
        return rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_MAP, self.room).u8(self.room.options.map)


@handler(ClientPacket.CLI_ROOM_CHANGE_OPTION, master=True, waiting=True)
class RoomChangeOptionRecv(RoomChangeBase):
    """settings u32: bytes 0-1 opções cruas, 2-3 modo. Mudar para um modo inválido é recusado."""

    def apply(self) -> bool:
        settings = self.buf.require(4).read_uint32()
        mode = RoomMode.parse(settings >> 16)
        if mode is None and settings >> 24:
            # comando /<evento> do cliente (ChooseEvent.txt): (settings & 0xFFFFF) | evento << 24, que também apaga o
            # bit 22 do Score. shortcut: mantém o modo atual e descarta o evento (efeito no original não mapeado)
            mode = self.room.options.mode
        if mode is None:
            return False
        self.room.options.mode, self.room.options.settings = mode, settings & 0xFFFF
        return True

    def lobby(self):
        return rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_SETTINGS, self.room).u32(rp.settings_of(self.room))


@handler(ClientPacket.CLI_ROOM_CHANGE_USEITEM, master=True, waiting=True)
class RoomChangeUseItemRecv(RoomChangeBase):
    def apply(self) -> bool:
        self.room.options.item_bytes = self.buf.require(8).read_bytes(8)
        return True


@handler(ClientPacket.CLI_ROOM_CHANGE_MAXMEN, master=True, waiting=True)
class RoomChangeMaxMenRecv(RoomChangeBase):
    """Não pode reduzir abaixo de quem já está na sala."""

    def apply(self) -> bool:
        capacity = self.buf.require(1).read_uint8()
        if capacity not in ROOM_SIZES or capacity < self.room.player_count():
            return False
        if any(p.slot >= capacity for p in self.room.players.values()):
            return False
        self.room.options.size = capacity
        return True

    def lobby(self):
        return rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_MAXMEN, self.room).u8(self.room.options.max_players())


@handler(ClientPacket.CLI_ROOM_CHANGE_TITLE, master=True, waiting=True)
class RoomChangeTitleRecv(RoomChangeBase):
    """Título no resto do corpo; 1 a 64 bytes, regra do servidor original."""

    def apply(self) -> bool:
        title = self.buf.read_bytes().split(b'\x00', 1)[0].decode('latin-1')
        if not 1 <= len(title) <= RoomOptions.MAX_RENAME:
            return False
        self.room.options.name = title
        return True

    def lobby(self):
        return rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_TITLE, self.room).raw(self.room.options.name.encode('latin-1'))


@handler(ClientPacket.CLI_ROOM_SELECT_TEAM, waiting=True)
class RoomSelectTeamRecv(GameRecv):
    """team u8 (0 = A, 1 = B). Time cheio (metade da capacidade) é recusado. 0x3211 para quem pediu."""

    async def handle(self):
        if not self.room.set_team(self.conn, self.buf.require(1).read_uint8()):
            return
        await self.conn.on_send(rp.ack(ServerPacket.SRV_ROOM_SELECT_TEAM))  # 0x3105 aqui fazia quem não é mestre reaplicar a sala da própria tela


@handler(ClientPacket.CLI_ROOM_USER_READY, waiting=True)
class RoomUserReadyRecv(GameRecv):
    """ready u8 (1 = pronto). O mestre não usa "pronto". Resposta 0x3231 = RTC + 00 00 (F3)."""

    async def handle(self):
        if self.room.set_ready(self.conn, self.buf.require(1).read_uint8() == 1):
            await self.conn.on_send(Packet.new(ServerPacket.SRV_ROOM_USER_READY, rtc=0).u16(0))


@handler(ClientPacket.CLI_ROOM_KICK, master=True, waiting=True)
class RoomKickRecv(GameRecv):
    """slot u8. O expulso recebe 0x3FFF; os demais, 0x3020 (pelo RoomManager.leave); o mestre, 0x315F (TH: 0x3151 + slot)."""

    async def handle(self):
        room = self.room
        target = await room.kick(self.conn, self.buf.require(1).read_uint8())
        if target is None:
            return
        await target.conn.on_send(Packet.new(ServerPacket.SRV_ROOM_KICKED))
        layout = phase.of(self.conn)
        reply = rp.ack(layout.kick_ack)
        await self.conn.on_send(reply.u8(target.slot) if layout.kick_ack == ServerPacket.SRV_ROOM_KICK_TH else reply)
