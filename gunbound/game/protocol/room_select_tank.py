from __future__ import annotations
from gunbound.base.enums import TANK_RANDOM, TANK_COUNT
from gunbound.game import room_packets as rp
from gunbound.game.protocol.base import GameRecv, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket


def valid_tank(t: int) -> bool:
    return t == TANK_RANDOM or 0 <= t < TANK_COUNT


@handler(ClientPacket.CLI_ROOM_SELECT_TANK)
class RoomSelectTankRecv(GameRecv):
    """
    0x3200: tanque primário u8 + secundário u8 (0xFF = aleatório; o secundário só vale no Tag).
    Grava também em ClientData[0:2] (seleção lembrada entre sessões, como antes).
    """

    async def handle(self):
        tank1, tank2 = self.buf.require(2).read_uint8(), self.buf.read_uint8()
        if not valid_tank(tank1) or not valid_tank(tank2):
            return
        room = self.room
        if room is not None and not room.set_tanks(self.conn, tank1, tank2):
            return  # em jogo: não troca
        game = self.conn.data['game']
        game['ClientData'] = bytes([tank1, tank2]) + bytes(game['ClientData'])[2:]
        # RTC 0: só nesse caso o cliente (0x4ec859) grava a escolha em [0x24328], de onde o 0x2121 tira o carro da vaga
        await self.conn.on_send(rp.ack(ServerPacket.SRV_ROOM_SELECT_TANK))
