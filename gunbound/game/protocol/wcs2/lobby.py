"""
Canal, megafone e convite do v584. Layouts lidos do GunBound.gme (VA); notas de análise em docs/Cliente v584 - pacotes.md.

0x7010 (vazio, 0x515143): sai no 0x2001 do 1o login, quando o cliente ainda está na lista de canais (flag +0x68780).
    0x7011 (global 0x4132db): u16 status (!= 0 = ignorado), u16 n, n x 34 bytes (apelido12, str8, u32, u32, u16,
    u16 grau, u16) para o XPRankingListDlg (dlg 0x25a, aba do 0x259 com as cotas por grau). A tela só desenha o ícone
    do grau e o apelido, 12 por página com rolagem, na ordem do pacote (0x54f310); os outros campos nunca são lidos
    (aqui: guilda, GP total, 0, posição, grau, 0). Lista = ranking geral por GP (CHANNEL_RANK primeiros).
0x7031 (push, 0x5151a2; nenhum pedido no cliente): quadro por país no XPReadyEventDlg (0x550170), que tem precedência
    no painel se alguma lista vier cheia (e o INI não tiver PumpkinEvent=1). u16 ignorado, 3 x u16 totais (ouro,
    prata, bronze), u16 n1, u16 n2, n1 x (u16 posição, u16 país, u32 pontos) - a última linha desce e mostra a
    posição: o país do jogador -, n2 x (u16, u16 país, u16 ouro, u16 prata, u16 bronze). Mandado logo depois do 0x7011.
    Sem fonte das regras: pontos = soma do GP do país; medalhas = jogadores do país entre os 10 / 50 / 100 primeiros
    do ranking. Config `country_board: false` não manda.
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
CHANNEL_RANK = 100
COUNTRY_ROWS = 10
MEDALS = (10, 50, 100)  # posição máxima para ouro, prata, bronze
RANKED = ("SELECT Id, Nickname, Guild, TotalGrade AS Grade, TotalScore AS Score, Country FROM Game "
          "WHERE TotalGrade <> 0 ORDER BY TotalScore DESC, Nickname")  # 0 = admin na escala do S2


def logged_in(clients) -> list:
    return gm.logged_in(clients)


def fixed(text: str, size: int) -> bytes:
    return text.encode('latin-1', 'replace')[:size].ljust(size, b'\x00')


def lobby_of(room) -> list:
    """Quem está no lobby (fora de sala) do canal onde a sala foi criada."""
    channel = getattr(room, 'channel', None)
    return [c for c in channel.clients.values() if c.room is None] if channel else []


def channel_rank_packet(rows: list) -> Packet:
    pkt = Packet.new(0x7011, rtc=0).u16(min(len(rows), CHANNEL_RANK))
    for pos, r in enumerate(rows[:CHANNEL_RANK], 1):
        pkt.raw(fixed(r['Nickname'], 12)).raw(fixed(r['Guild'] or '', 8)).u32(max(int(r['Score'] or 0), 0)).u32(0)
        pkt.u16(pos).u16(int(r['Grade'] or 0)).u16(0)
    return pkt


def country_board_packet(rows: list, my_country: int) -> Packet:
    """0x7031 a partir do ranking geral (linhas com Country e Score, já ordenadas)."""
    points, medals = {}, {}
    for pos, r in enumerate(rows, 1):
        country = int(r['Country'] or 0)
        if country <= 0:
            continue
        points[country] = points.get(country, 0) + max(int(r['Score'] or 0), 0)
        kind = next((i for i, top in enumerate(MEDALS) if pos <= top), None)
        if kind is not None:
            medals.setdefault(country, [0, 0, 0])[kind] += 1
    ranked = sorted(points, key=lambda c: (-points[c], c))
    top = ranked[:COUNTRY_ROWS]
    if my_country in points:  # última linha: o país do jogador, com a posição
        top = [c for c in top if c != my_country][:COUNTRY_ROWS - 1] + [my_country]
    table = sorted(medals, key=lambda c: [-m for m in medals[c]] + [c])[:COUNTRY_ROWS]
    totals = [sum(m[i] for m in medals.values()) for i in range(3)]
    pkt = Packet.new(0x7031).u16(0).u16(totals[0]).u16(totals[1]).u16(totals[2]).u16(len(top)).u16(len(table))
    for c in top:
        pkt.u16(ranked.index(c) + 1).u16(c).u32(points[c])
    for c in table:
        pkt.u16(0).u16(c).u16(medals[c][0]).u16(medals[c][1]).u16(medals[c][2])
    return pkt


@handler(0x7010, register=False)
class ChannelInfoRecv(GameRecv):
    @inject
    async def handle(self, db=Provide['database']):
        rows = await db.fetch_all(RANKED)
        await self.conn.on_send(channel_rank_packet(rows))
        if self.conn.server.config.get('country_board', True):
            my_country = int((self.conn.data.get('game') or {}).get('Country') or 0)
            await self.conn.on_send(country_board_packet(rows, my_country))


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
