"""Configuração da sala pelo mestre (0x3100..0x3104), time (0x3210), pronto (0x3230) e expulsão (0x3150)."""
from __future__ import annotations
from gunbound.base.enums import RoomMode, RoomOptions, MAP_COUNT
from gunbound.game.stage_pos import out_of_range, valid_settings
from gunbound.game import room_packets as rp, phase
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket


class RoomChangeBase(GameRecv):
    """Só o mestre e só com a sala aguardando (guardas). `apply()` valida e altera; 0x3105 para o mestre, 0x3400 para os outros."""

    drop = False  # original: validação de settings/mapa falhou -> o handler devolve falso e a conexão cai

    def apply(self) -> bool:
        raise NotImplementedError

    def lobby(self):
        """Pacote 0x21F2..0x21F6 para a lista de salas do lobby, ou None."""
        return None

    async def handle(self):
        if not self.apply():
            if self.drop:
                print(f"[{self.conn.addr}] {type(self).__name__}: settings/mapa fora do que o cliente gera, derrubando")
                await self.conn.close()
            return
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
        if not valid_settings(self.room.options.settings, stage, phase.of(self.conn).stage_pos):   # original 0x4166f0 -> 0x406700
            self.drop = out_of_range(self.room.options.settings, stage)
            return False
        self.room.options.map = stage
        return True

    def lobby(self):
        return rp.lobby_room(ServerPacket.SRV_LOBBY_ROOM_MAP, self.room).u8(self.room.options.map)


@handler(ClientPacket.CLI_ROOM_CHANGE_OPTION, master=True, waiting=True)
class RoomChangeOptionRecv(RoomChangeBase):
    """settings u32 gravado cru, como o original (0x4167c0): inclusive o lado (bits 16-17) e o evento (bits 24-31, comando
    /evento do cliente). Validação do original (0x406700): posições < 3, lado < 4 e o mapa com vaga no stage_pos; o
    original derruba a conexão quando falha. Aqui só derruba no que não depende da tabela (posições >= 3, mapa >= 20):
    a tabela do TH (2006) só tem os lados A/B, então faltar linha nela só recusa."""

    def apply(self) -> bool:
        settings = self.buf.require(4).read_uint32()
        if not valid_settings(settings, self.room.options.map, phase.of(self.conn).stage_pos):
            self.drop = out_of_range(settings, self.room.options.map)
            return False
        self.room.options.settings = settings
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
        if capacity not in self.room.options.sizes() or capacity < self.room.player_count():
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
