"""
Keepalive, opcodes enviados pelo cliente ainda sem layout (só registrados para não cair no dump de "desconhecido"),
e salvar avatar (0x600E). Comandos de GM ficam em gm_commands.py.
"""
from __future__ import annotations
import time
from dependency_injector.wiring import Provide, inject
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket

MAX_AVATAR_ITEMS = 8


@handler(ClientPacket.CLI_KEEPALIVE, auth=False)
class KeepAliveRecv(GameRecv):
    async def handle(self):
        self.conn.last_activity = time.time()

    def log_command(self, conn):
        pass  # frequente demais para logar


class SilentRecv(GameRecv):
    """Opcode conhecido do cliente, sem layout/resposta confirmados: registra atividade e loga."""

    async def handle(self):
        self.conn.last_activity = time.time()


for _cmd in (ClientPacket.CLI_UNKNOWN_1004,
             ClientPacket.CLI_ROOM_GRANDPRIX_BEGIN, ClientPacket.CLI_ROOM_GRANDPRIX_CANCEL):
    handler(_cmd, auth=False)(type(f"Silent{int(_cmd):04X}Recv", (SilentRecv,), {"__module__": __name__}))


@handler(ClientPacket.CLI_ITEM_WEAR)
class AvatarSaveRecv(GameRecv):
    """
    0x600E: count u16 + count x (chest_id u32, vestir u8 1/0). Visto no cliente: 02 00 03000000 01 04000000 01.
    Itens que não são do jogador (ou expirados) recusam o pedido (0x600F rtc 1).
    Guarda os ItemNo vestidos em conn.data['avatar'] e (nível de encantamento, selo) em conn.data['avatar_enchant']
    (usados no bloco de avatar da sala).
    """

    @inject
    async def handle(self, inventory_repository=Provide['inventory_repository']):
        count = self.buf.require(2).read_uint16()
        changes = [(self.buf.require(5).read_uint32(), self.buf.read_uint8()) for _ in range(min(count, 64))]
        chest = {int(c['No']): c for c in await inventory_repository.get_chest(self.user_id())}
        expired = lambda c: c['Expire'] is not None and c['Expire'] <= 0
        if any(i not in chest or (wear and expired(chest[i])) for i, wear in changes):
            await self.conn.on_send(Packet.new(ServerPacket.SRV_ITEM_WEAR, rtc=1))
            return
        avatar = list(self.conn.data.get('avatar', []))
        enchant = self.conn.data.setdefault('avatar_enchant', {})
        for i, wear in changes:
            item = int(chest[i]['Item'])
            if wear:
                enchant[item] = (int(chest[i].get('EnchantLevel') or 0), int(chest[i].get('Seal') or 0))
            if wear and item not in avatar:
                avatar.append(item)
            elif not wear and item in avatar:
                avatar.remove(item)
        self.conn.data['avatar'] = avatar[:MAX_AVATAR_ITEMS]
        await inventory_repository.update_wearing(self.user_id(), changes)
        await self.conn.on_send(Packet.new(ServerPacket.SRV_ITEM_WEAR, rtc=0))
