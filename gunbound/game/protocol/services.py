"""
Serviços extraídos do servidor original via REA (endereços em docs/Opcodes do servidor original.md).
Resposta = opcode + 1 (função 0x428040 do original), salvo indicação.
"""
from __future__ import annotations
from dependency_injector.wiring import Provide, inject
from gunbound.game.protocol.base import GameRecv, Packet, decrypt_blocks, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.util.binary_buffer import PacketError

ID_LEN = 16
NICK_LEN = 12
MAX_ACCUSE_REASON = 0x40
MAX_ACCUSE_EXTRA = 0x96A
MAX_GIFT_MSG = 0x32
RTC_FAIL = 1


def cstr(data: bytes) -> str:
    return data.split(b'\x00', 1)[0].decode('latin-1')


class EncryptedRecv(GameRecv):
    """Corpo cifrado em blocos de 16 (prefixo do comando + 12 bytes). Pacote inválido é descartado com log."""

    def body(self):
        try:
            return decrypt_blocks(self.conn, self.buf.read_bytes(), self.command)
        except PacketError as e:
            print(f"[{self.conn.addr}] 0x{self.command:04X} inválido: {e}")
            return None


# 0x1016 SVC_REP_AUTHDWORD (0x42872d): resposta do cliente ao desafio anti-hack (12 bytes cifrados); o original
# confere o dword numa lista de desafios enviados. Não implementado: este servidor não envia desafios.
# @handler(ClientPacket.CLI_REP_AUTHDWORD)
# class RepAuthDwordRecv(EncryptedRecv):
#     async def handle(self):
#         if self.body() is not None:
#             await self.conn.on_send(Packet.new(ServerPacket.SRV_REP_AUTHDWORD, rtc=0))


@handler(ClientPacket.CLI_USER_NICK)
class UserNickRecv(GameRecv):
    """0x1021 (0x42887e): u16 qtd + qtd x Id(16). Resposta 0x1022: u16 achados + achados x (Id 16 + Nickname 12)."""

    @inject
    async def handle(self, user_repository=Provide['user_repository']):
        count = self.buf.read_uint16()
        if self.buf.remaining() != count * ID_LEN:
            return
        ids = [cstr(self.buf.read_bytes(ID_LEN)) for _ in range(count)]
        found = await user_repository.get_nicknames([i for i in ids if i])
        pkt = Packet.new(ServerPacket.SRV_USER_NICK).u16(len(found))
        for user in found:
            pkt.fixed(user['Id'], ID_LEN).fixed(user['Nickname'], NICK_LEN)
        await self.conn.on_send(pkt)




@handler(ClientPacket.CLI_PLAY_DROP_USER, in_game=True)
class PlayDropUserRecv(EncryptedRecv):
    """
    0x4000 (0x429cae -> FUN_00416d50 'CGameRoomManager::DropSlot'): 1º byte = slot a derrubar (< 8).
    O original manda 0x400F (sem corpo) para o jogador do slot e avisa o banco; o cliente dele sai sozinho.
    """

    async def handle(self):
        body = self.body()
        if body is None or not body.remaining():
            return
        target = self.room.player_by_slot(body.read_uint8())
        if target is None or self.room.player(self.conn) is None:
            print(f"[{self.conn.addr}] DropSlot: slot inválido")
            return
        await target.conn.on_send(Packet.new(ServerPacket.SRV_PLAY_DROP_USER))


@handler(ClientPacket.CLI_POLICE_ACCUSE)
class PoliceAccuseRecv(EncryptedRecv):
    """
    0x5000 (0x429db5): Nickname(16) + u8 tamanho (<= 64) + motivo + u16 tamanho (<= 0x96A) + anexo (log do chat).
    Grava na tabela Accuse e confirma em 0x5001 (RTC 0).
    """

    @inject
    async def handle(self, server_repository=Provide['server_repository']):
        body = self.body()
        if body is None or body.remaining() < ID_LEN + 1:
            return
        accused = cstr(body.read_bytes(ID_LEN))
        size = body.read_uint8()
        if size > MAX_ACCUSE_REASON or body.remaining() < size:
            return
        reason = cstr(body.read_bytes(size))
        if body.remaining() >= 2:
            extra = body.read_uint16()
            if extra <= min(MAX_ACCUSE_EXTRA, body.remaining()):
                reason = f"{reason}\n{cstr(body.read_bytes(extra))}".strip()
        cfg = self.conn.server.config
        await server_repository.insert_accuse(self.user_id(), cfg['host'], cfg['port'], accused, reason)
        await self.conn.on_send(Packet.new(ServerPacket.SRV_POLICE_ACCUSE, rtc=0))


@handler(ClientPacket.CLI_ITEM_LOCATION)
class ItemLocationRecv(GameRecv):
    """0x600A (0x42acd7): u16 qtd + qtd x (chest u32, posição u32); tamanho exato qtd*8+2. Resposta 0x600B RTC 0."""

    @inject
    async def handle(self, inventory_repository=Provide['inventory_repository']):
        count = self.buf.read_uint16()
        if self.buf.remaining() != count * 8:
            return
        places = [(self.buf.read_uint32(), self.buf.read_uint32()) for _ in range(count)]
        await inventory_repository.update_place_order(self.user_id(), places)
        await self.conn.on_send(Packet.new(ServerPacket.SRV_ITEM_LOCATION, rtc=0))


@handler(ClientPacket.CLI_ITEM_GIFT)
class ItemGiftRecv(EncryptedRecv):
    """
    0x6028 (0x42b276), cifrado, até 0x54 bytes: Id do destinatário(16) + 12 bytes (chest u32 + 8 [INVESTIGAR])
    + u8 tamanho (<= 0x32) + mensagem. Passa o item (não vestido) do próprio baú. Resposta 0x6029 RTC 0 / 1.
    """

    @inject
    async def handle(self, inventory_repository=Provide['inventory_repository'], user_repository=Provide['user_repository']):
        body = self.body()
        if body is None or body.remaining() < ID_LEN + 13:
            return
        receiver = cstr(body.read_bytes(ID_LEN))
        chest_id = body.read_uint32()
        body.read_bytes(8)
        size = body.read_uint8()
        if size > MAX_GIFT_MSG or not receiver or receiver == self.user_id():
            return await self.reply(RTC_FAIL, f"pedido inválido para '{receiver}'")
        if await user_repository.get_profile(receiver) is None:
            return await self.reply(RTC_FAIL, f"destinatário '{receiver}' não existe")
        if not await inventory_repository.transfer_chest(chest_id, self.user_id(), receiver):
            return await self.reply(RTC_FAIL, f"item {chest_id} não é do jogador ou está vestido")
        await self.reply(ServerCode.SRV_OK, f"item {chest_id} enviado para '{receiver}'")

    async def reply(self, rtc: int, log: str):
        print(f"[{self.conn.addr}] SVC_ITEM_GIFT: {log}")
        await self.conn.on_send(Packet.new(ServerPacket.SRV_ITEM_GIFT, rtc=rtc))
