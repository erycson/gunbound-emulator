"""
Serviços extraídos do servidor original via REA (endereços em docs/Opcodes do servidor original.md).
Resposta = opcode + 1 (função 0x428040 do original), salvo indicação.
"""
from __future__ import annotations
import time
from datetime import datetime
from dependency_injector.wiring import Provide, inject
from gunbound.game.protocol.base import GameRecv, Packet, decrypt_blocks, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.util.binary_buffer import PacketError

ID_LEN = 16
NICK_LEN = 12
MAX_ACCUSE_REASON = 0x40
MAX_ACCUSE_EXTRA = 0x96A
MAX_GIFT_MSG = 0x32
RTC_FAIL = 4    # 0x6029 do original: 0 ok, 4 qualquer falha


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


class AntiCheatAnswerRecv(GameRecv):
    """Respostas do anti-hack: 0x1016 (GameGuard CSAuth2, 16 bytes sem a cifra da sessão), 0x1019/0x101C (HackShield).
    Corpo cru, sem decrypt_blocks: quem decide é gunbound/game/anticheat.py (off: só registra)."""

    async def handle(self):
        self.conn.last_activity = time.time()
        body = self.buf.read_bytes()
        if self.conn.anticheat is None:
            print(f"[anticheat] 0x{self.command:04X} antes do anti-hack da sessão existir ({len(body)} bytes), ignorado")
            return
        await self.conn.anticheat.on_answer(self.command, body)


for _cmd in (ClientPacket.CLI_REP_AUTHDWORD, ClientPacket.CLI_HS_ACK, ClientPacket.CLI_HS_GUID_ACK):
    handler(_cmd)(type(f"AntiCheat{int(_cmd):04X}Recv", (AntiCheatAnswerRecv,), {"__module__": __name__}))


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
    0x6028, cifrado, até 0x54 bytes (servidores 2006 e 2007, asm 0x42eb6d; cliente TH 0x4d5a12): u32 ChestNo,
    char[16] Id do destinatário, char[12] apelido, u8 tamanho (<= 0x32) + mensagem. Passa um item C/G não recuperado
    do próprio baú (vestido ou não; vira 'T') e grava GiftMsg/ReceiptGift. Resposta 0x6029 RTC 0 / 4.
    GiftProhibitTime no futuro ou mensagem > 0x32: o handler original devolve falso e a conexão cai (2007 0x42eba7).
    Doar o SuperUserItem tira o power user da sessão, como o original zera o prazo. VIP/Event não existem na config.
    Destinatário inexistente ou o próprio jogador: RTC 4 (o original não confere; o item sumiria).
    """

    @inject
    async def handle(self, inventory_repository=Provide['inventory_repository'], user_repository=Provide['user_repository']):
        body = self.body()
        if body is None or body.remaining() < 4 + ID_LEN + NICK_LEN + 1:
            return
        chest_id = body.read_uint32()
        receiver = cstr(body.read_bytes(ID_LEN))
        nick = cstr(body.read_bytes(NICK_LEN))
        size = body.read_uint8()
        prohibit = (self.conn.data.get('game') or {}).get('GiftProhibitTime')
        if size > MAX_GIFT_MSG or size > body.remaining() or (prohibit is not None and prohibit > datetime.now()):
            print(f"[{self.conn.addr}] SVC_ITEM_GIFT: mensagem inválida ou GiftProhibitTime {prohibit}; derrubando")
            return await self.conn.close()
        msg = body.read_bytes(size).decode('latin-1')
        if not receiver or receiver == self.user_id():
            return await self.reply(RTC_FAIL, f"pedido inválido para '{receiver}'")
        if await user_repository.get_profile(receiver) is None:
            return await self.reply(RTC_FAIL, f"destinatário '{receiver}' não existe")
        item = await inventory_repository.transfer_chest(chest_id, self.user_id(), receiver, nick, msg)
        if item is None:
            return await self.reply(RTC_FAIL, f"item {chest_id} não é do jogador ou não é C/G não recuperado")
        if item == self.conn.server.config.get('super_user_item'):
            self.conn.data['power_user'] = False
        await self.reply(ServerCode.SRV_OK, f"item {chest_id} enviado para '{receiver}'")

    async def reply(self, rtc: int, log: str):
        print(f"[{self.conn.addr}] SVC_ITEM_GIFT: {log}")
        await self.conn.on_send(Packet.new(ServerPacket.SRV_ITEM_GIFT, rtc=rtc))
