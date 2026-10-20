from __future__ import annotations
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import RoomMode, RoomOptions, ROOM_SIZES, STAGE_SIZES, RANDOM_MAP
from gunbound.game.stage_pos import valid_settings
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game import room_packets as rp, phase
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode


@handler(ClientPacket.CLI_ROOM_CREATE, channel=True)
class RoomCreateRecv(GameRecv):
    """
    0x2120: title_len u8 + title + settings u32 (cru; o cliente mascara com 0xFFFFF) + senha str[4] + capacidade u8.
    Resposta 0x2121 (sem RTC): 00 00 00 | room_id u16 | MOTD.
    """

    @inject
    async def handle(self, rooms=Provide['rooms']):
        if self.conn.room is not None:
            return
        size = self.buf.require(1).read_uint8()
        if not 1 <= size <= RoomOptions.MAX_TITLE:
            return
        name = self.buf.require(size + 9).read_string(size, encoding='latin-1')
        settings = self.buf.read_uint32()
        raw_pwd = self.buf.read_bytes(4)
        capacity = self.buf.read_uint8()
        stage = None
        if phase.is_stage(self.conn):  # v584 0x52e0e0: capacidade = MaxMan (1/2) e mais u16 StageNum-1, u8 GameMode
            extra = self.buf.require(3)
            stage = (extra.read_uint16(), extra.read_uint8())

        settings |= (int(self.conn.server.config.get('stage_event') or 0) & 0xFF) << 24  # StageEvent do original, só aqui
        mode = RoomMode.of_settings(settings)
        if capacity not in (STAGE_SIZES if stage else ROOM_SIZES) or not valid_settings(settings, RANDOM_MAP, phase.of(self.conn).stage_pos):
            print(f"[{self.conn.addr}] Criar sala: settings 0x{settings:08X} ou capacidade {capacity} inválidos")
            await self.conn.on_send(rp.room_error(ServerPacket.SRV_ROOM_CREATE, ServerCode.SRV_ROOM_CREATE_FAIL))
            return
        # Às vezes vem lixo depois do primeiro byte da senha
        password = None if raw_pwd[0] == 0 else raw_pwd.split(b'\x00', 1)[0].decode('latin-1')

        options = RoomOptions(name, mode, capacity, password, settings=settings, stage=stage)
        room = await rooms.create(self.conn, options)
        if room is None:
            await self.conn.on_send(rp.room_error(ServerPacket.SRV_ROOM_CREATE, ServerCode.SRV_ROOM_CREATE_FAIL))
            return
        await self.conn.on_send(Packet.new(ServerPacket.SRV_ROOM_CREATE).raw(b'\x00' * 3).u16(room.id)
                                .text(rooms.motd()))
