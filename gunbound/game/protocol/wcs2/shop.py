r"""
WCS2 (cliente v584): presentes, desconto e Rena na loja. Endereços do GunBound.gme do v584 (análise estática, Ghidra).

0x6004 (vazio, sai no login ok): o v584 NÃO tem leitor do 0x6004 de resposta; quer um 0x6005 por presente (global 0x41256b),
    sem RTC: u32 item (GiftMsg.MenuId), u32 GiftMsg.No (chave, o cliente descarta repetidos), u8 1, apelido12, u32 time_t,
    u8 len, texto. O len não é conferido: mais de 0x83 bytes estoura o registro do cliente, então corta em 0x82.
    A resposta do jogador ao popup sai pelo 0x6008, que já existe.
0x7118 (u8 modo, ShopMode 0x51a170): desconto da loja. Modo 1 sai sozinho a cada entrada na loja; 2 exige 50 pontos e
    3 exige 100 (G+0x1b828). O cliente multiplica os 10 preços por 1.0/0.8/0.5 e trunca; o 0x6020 não leva o modo,
    então o servidor guarda o fator na conexão e o item_buy aplica.
    0x7119: u16 rtc; rtc 0 -> u32 pontos (G+0x1b828); rtc != 0 -> o cliente volta ao modo 1.
    O mesmo campo é gravado pelo push 0x7117; como o modo 1 é pedido a cada entrada na loja, o 0x7119 já basta.
0x7124 (u32 = 100 constante, XPRenaDlg 0x55f5d0) -> 0x7125: u16 rtc; rtc 0 -> u32 item ganho + u32 saldo (G+0x1b82c).
    O cliente não debita nem insere o item no baú. O botão só habilita com saldo >= 100, que vem do push 0x7123
    (u16 0 + u32), mandado junto da resposta do 0x7012 (login).
0x7136 (vazio, uma vez por entrada na loja, botão 0xBB) -> 0x7137 u16 rtc 0: o cliente só redesenha a lista.

Pontos de desconto e de Rena: colunas Game.DiscountPoints e Game.RenaPoints (db/linked.sql).
O cliente não mostra de onde esses pontos vêm; hoje só por SQL.
"""
from __future__ import annotations
import random
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import AcquisitionType, ExpireType
from gunbound.game.protocol.base import GameRecv, Packet, handler

CLI_GIFT_MSG, SRV_GIFT = 0x6004, 0x6005
CLI_DISCOUNT, SRV_DISCOUNT = 0x7118, 0x7119
CLI_RENA, SRV_RENA, SRV_RENA_POINTS = 0x7124, 0x7125, 0x7123
CLI_SHOP_ENTER, SRV_SHOP_ENTER = 0x7136, 0x7137
GIFT_TEXT_MAX = 0x82
DISCOUNT = {1: (0, 1, 1), 2: (50, 4, 5), 3: (100, 1, 2)}  # modo: (pontos, numerador, denominador)
RENA_COST = 100
REFUSE = 1


def gift_packet(msg: dict) -> Packet:
    text = (msg['Msg'] or '').encode('latin-1', 'replace')[:GIFT_TEXT_MAX]
    return (Packet.new(SRV_GIFT).u32(msg['MenuId']).u32(msg['No']).u8(1).fixed(msg['Sender'], 12)
            .u32(int(msg['SentTime'].timestamp())).u8(len(text)).raw(text))


def rena_points_packet(points: int) -> Packet:
    return Packet.new(SRV_RENA_POINTS, rtc=0).u32(points)


@handler(CLI_GIFT_MSG, register=False)
class GiftMsgRecv(GameRecv):
    @inject
    async def handle(self, user_repository=Provide['user_repository']):
        for msg in await user_repository.get_gift_msgs(self.user_id()):
            await self.conn.on_send(gift_packet(msg))


@handler(CLI_DISCOUNT, register=False)
class DiscountRecv(GameRecv):
    @inject
    async def handle(self, user_repository=Provide['user_repository']):
        mode = self.buf.require(1).read_uint8()
        self.conn.data['shop_discount'] = (1, 1)
        if mode not in DISCOUNT:
            return await self.conn.on_send(Packet.new(SRV_DISCOUNT, rtc=REFUSE))
        cost, num, den = DISCOUNT[mode]
        if cost and not await user_repository.add_points(self.user_id(), 'DiscountPoints', -cost):
            return await self.conn.on_send(Packet.new(SRV_DISCOUNT, rtc=REFUSE))
        self.conn.data['shop_discount'] = (num, den)
        points = await user_repository.get_points(self.user_id(), 'DiscountPoints')
        await self.conn.on_send(Packet.new(SRV_DISCOUNT, rtc=0).u32(points))


@handler(CLI_RENA, register=False)
class RenaRecv(GameRecv):
    @inject
    async def handle(self, user_repository=Provide['user_repository'], inventory_repository=Provide['inventory_repository']):
        self.buf.require(4).read_uint32()  # o cliente manda 100 fixo; o custo é do servidor
        prizes = self.conn.server.config.get('rena') or []
        user_id = self.user_id()
        if not prizes or not await user_repository.add_points(user_id, 'RenaPoints', -RENA_COST):
            return await self.conn.on_send(Packet.new(SRV_RENA, rtc=REFUSE))
        item, count, _ = random.choices(prizes, weights=[int(w) for *_, w in prizes])[0]
        await inventory_repository.insert_chest(user_id, int(item), AcquisitionType.Gift, ExpireType.Infinite, None, int(count))
        points = await user_repository.get_points(user_id, 'RenaPoints')
        print(f"[{self.conn.addr}] Rena: item {int(item):X} x{count}, saldo {points}")
        await self.conn.on_send(Packet.new(SRV_RENA, rtc=0).u32(int(item)).u32(points))


@handler(CLI_SHOP_ENTER, register=False)
class ShopEnterRecv(GameRecv):
    async def handle(self):
        await self.conn.on_send(Packet.new(SRV_SHOP_ENTER, rtc=0))
