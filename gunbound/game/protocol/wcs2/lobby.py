"""
Canal, megafone e convite do v584. Layouts lidos do GunBound.gme (VA); notas de análise em docs/Cliente v584 - pacotes.md.

0x7010 (vazio, 0x515143): sai no 0x2001 do 1o login, quando o cliente ainda está na lista de canais (flag +0x68780).
    0x7011 (global 0x4132db): u16 status, u16 n, n x 34 bytes (apelido12, str8, u32, u32, u16, u16 grau, u16) para o
    diálogo 0x25a. Nenhuma resposta leva o cliente ao lobby: ele reconecta quando o jogador clica num canal.
    shortcut: lista vazia (o que cada campo significa não foi fechado).
0x6054 (0x5266c0 e outros): "usar item", 17 bytes: u8 subtipo, u16, u32 serial (Chest.No), u32, u16, u32.
    Só o subtipo 2 (megafone, item 0xAAE6E) está implementado. 0x6055 (global 0x412786): u16 status, u32 serial,
    u32 restante, u32 item; status != 0 vira erro (0x6020 = "SlotNumber Error").
    Com status 0 e item 0xAAE6E o cliente manda 0x5010 (cifrado) com u8 tipo 8, u8 cor 0..3, u8 tamanho, texto
    ("apelido] msg"); o servidor repassa a todos como 0x5011 em claro, mesmo layout (handler 0x411360).
0x3450 (vazio, sala) -> 0x3451 (cena Ready 0x50936d): u16 n + n x 17 (u16 0, u16 grau (0 = cliente não convida),
    u8 sexo, apelido12): quem está no lobby do mesmo canal.
0x3452 (sala, 0x5514f5): u16 sala, senha4, msg20, apelido12 do convidado; sem resposta. O convidado, se estiver no lobby,
    recebe 0x2025 (lobby 0x4d607b): u16 sala, senha4, msg20, apelido12 de quem convidou. O aceite é um 0x2110 comum.
"""
from __future__ import annotations
from dependency_injector.wiring import Provide, inject
from gunbound.game.protocol.base import GameRecv, Packet, decrypt_blocks, handler
import gunbound.game.protocol.gm_commands as gm  # módulo, não nomes: o phase.py importa este arquivo no meio do gm_commands
from gunbound.util.binary_buffer import PacketError

MEGAPHONE_ITEM = 0xAAE6E
USE_MEGAPHONE = 2
ITEM_USE_ERROR = 0x6020
BCM_MEGAPHONE = 8


def logged_in(clients) -> list:
    return gm.logged_in(clients)


def fixed(text: str, size: int) -> bytes:
    return text.encode('latin-1', 'replace')[:size].ljust(size, b'\x00')


def lobby_of(room) -> list:
    """Quem está no lobby (fora de sala) do canal onde a sala foi criada."""
    channel = getattr(room, 'channel', None)
    return [c for c in channel.clients.values() if c.room is None] if channel else []


@handler(0x7010, register=False)
class ChannelInfoRecv(GameRecv):
    async def handle(self):
        await self.conn.on_send(Packet.new(0x7011, rtc=0).u16(0))


@handler(0x6054, register=False)
class ItemUseRecv(GameRecv):
    @inject
    async def handle(self, inventory_repository=Provide['inventory_repository']):
        buf = self.buf.require(7)
        kind, _ = buf.read_uint8(), buf.read_uint16()
        serial = buf.read_uint32()
        user_id = self.conn.data['profile']['Id']
        item = await inventory_repository.get_chest_item(user_id, serial) if kind == USE_MEGAPHONE else None
        if not item or int(item['Item']) != MEGAPHONE_ITEM or int(item['Volume'] or 0) <= 0:
            print(f"[{self.conn.addr}] 0x6054 recusado: subtipo {kind}, serial {serial}")
            await self.conn.on_send(Packet.new(0x6055, rtc=ITEM_USE_ERROR))
            return
        await inventory_repository.chest_consume(user_id, serial, 1)
        self.conn.data['megaphone'] = True  # libera um 0x5010 tipo 8
        await self.conn.on_send(Packet.new(0x6055, rtc=0).u32(serial).u32(int(item['Volume']) - 1).u32(MEGAPHONE_ITEM))


@handler(0x5010, register=False)
class BcmV584Recv(GameRecv):
    """0x5010 do v584: u8 tipo, u8 cor, u8 tamanho, texto. Tipo 8 = megafone (de quem acabou de gastar o item);
    os outros tipos seguem só para GM, como o BcmRecv antigo."""

    @inject
    async def handle(self, clients=Provide['clients']):
        try:
            body = decrypt_blocks(self.conn, self.buf.read_bytes(), self.command)
            kind, color, size = body.read_uint8(), body.read_uint8(), body.read_uint8()
            text = body.read_bytes(min(size, body.remaining())).split(b'\x00', 1)[0].decode('latin-1')
        except PacketError as e:
            print(f"[{self.conn.addr}] 0x5010 inválido: {e}")
            return
        if kind == BCM_MEGAPHONE and self.conn.data.pop('megaphone', False):
            # o apelido vem da sessão, não do texto do cliente
            msg = f"{self.conn.data['profile']['Nickname']}] {text.split('] ', 1)[-1]}".encode('latin-1', 'replace')[:255]
            pkt = lambda: Packet.new(0x5011).u8(BCM_MEGAPHONE).u8(color if color <= 3 else 0).u8(len(msg)).raw(msg)
            for c in logged_in(clients):
                await c.on_send(pkt())
        elif gm.is_gm(self.conn):
            for c in logged_in(clients):
                await c.on_send(gm.text_packet(text))


@handler(0x3450, room=True, register=False)
class InviteListRecv(GameRecv):
    async def handle(self):
        lobby = [c for c in lobby_of(self.room) if c is not self.conn]
        pkt = Packet.new(0x3451).u16(len(lobby))
        for c in lobby:
            grade = c.data['game'].get('TotalGrade') or 1
            pkt.u16(0).u16(max(int(grade), 1)).u8(c.data['profile'].get('Gender') or 0).raw(fixed(c.data['profile']['Nickname'], 12))
        await self.conn.on_send(pkt)


@handler(0x3452, room=True, register=False)
class InviteSendRecv(GameRecv):
    async def handle(self):
        buf = self.buf.require(38)
        room_id, password, msg = buf.read_uint16(), buf.read_bytes(4), buf.read_bytes(20)
        nick = buf.read_bytes(12).split(b'\x00', 1)[0].decode('latin-1').lower()
        target = next((c for c in lobby_of(self.room) if c.data['profile']['Nickname'].lower() == nick), None)
        if target is None or room_id != self.room.id:
            return
        await target.on_send(Packet.new(0x2025).u16(room_id).raw(password).raw(msg)
                             .raw(fixed(self.conn.data['profile']['Nickname'], 12)))
