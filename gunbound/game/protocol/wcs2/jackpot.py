"""
Jackpot (CPopup_JackpotBomb, tela "Jack Pot Booster Card") do cliente v584.

Como era no oficial (loja Softnyx BR e vídeo "Gunbound Jackpot itens", 2010): as cartas Normal/Rare/Epic/Legend
Jackpot Booster Card são compradas na Avatar Shop; cada carta aberta dá "bônus de gold e um item de maneira aleatória".
No vídeo o 1º slot é sempre o gold e os seguintes são itens ou "Boost Failed"; a Legend dá 2 itens.

0x6056 (0x51d579, envia ao abrir a carta): u8 carta [popup+0x8c] (0 Normal, 1 Rare, 2 Epic, 3 Legend), u32 campo +4
da entrada do baú local (0x441e40), u32 item da carta = 0xAAEBF + carta. O cliente só manda se tiver o item com volume > 0.
0x6057 (0x412fbd): u16 RTC; RTC != 0 -> popup[0xb0] = 0 (libera o botão). RTC 0 ->
  u32 item da carta, u8 volume novo (0x435900: acha no baú pelo item, grava o volume, remove se 0),
  u8 -> global+0x6f644, e o resto vai para o popup (0x51db70, flag 1): u16 a, u16 b, a+b registros.
  Os a primeiros vão para os slots (popup+0xc0), os b para popup+0xd0.
Registro (0x51dc33): u32 tipo, u32 No do baú, u32 item, u8 ?, u8 ?, u8 tem_prazo [u32 segundos], u8 tem_qtd [u32 qtd],
  u8 f2 [u32]. Tipo 0 = falhou ("Boost Failed"), 1 = gold ("%d"), outro = item: o cliente põe no baú local na hora
  (0x4357e0/0x41b7b0/0x41b8f0/0x41b9b0 conforme a faixa do item) com nome + "%3d EA".
O gold na tela é atualizado com 0x6105 (cliente 0x41328e grava em global+0x1b820).
shortcut: os campos "?" e o u8 do global+0x6f644 vão em 0.
0x6058 (Jackpot Bomb, 0x51e370): u8 carta (1 Rare, 2 Epic), u32 No da carta no baú, u32 0xAAEBF + carta. O cliente
  exige volume >= 12 (Rare) / 15 (Epic). 0x6059 (0x41304b): u16 RTC; RTC 0 -> u32 item da carta, u8 volume novo e UM
  registro como os do 0x6057 (o cliente põe o prêmio no baú local, 0x51db70 flag 0, e manda 0x6104).
  Prêmio: config `jackpot_bomb` {carta: [item, qtd]}; padrão = 1 carta do nível seguinte.
"""
import random
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import AcquisitionType, ExpireType
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.gold import GoldResp
from gunbound.game.protocol.wcs2.enchant import REFUSED

CLI_JACKPOT, SRV_JACKPOT = 0x6056, 0x6057
CLI_JACKPOT_BOMB, SRV_JACKPOT_BOMB = 0x6058, 0x6059
CARD_ITEM = 0xAAEBF  # + carta (0..3)
KIND_FAIL, KIND_GOLD, KIND_ITEM = 0, 1, 2


def record(kind: int, chest_no: int = 0, item: int = 0, count: int = 0) -> bytes:
    """Um registro do 0x6057 (falha, gold ou item)."""
    pkt = Packet.new(0).u32(kind).u32(chest_no).u32(item).u8(0).u8(0).u8(0)  # sem prazo
    pkt.u8(1).u32(count) if kind != KIND_FAIL else pkt.u8(0)
    return bytes(pkt.u8(0).buf.getvalue()[2:])  # sem o cmd 0


def jackpot_ok(card_item: int, volume: int, records: list[bytes]) -> Packet:
    return (Packet.new(SRV_JACKPOT, rtc=0).u32(card_item).u8(volume).u8(0)
            .u16(len(records)).u16(0).raw(b''.join(records)))


def draw(rule: dict) -> tuple[int, list]:
    """(gold, [(item, qtd) ou None se falhou]) de uma carta. rule = config['jackpot'][carta]."""
    lo, hi = rule.get('gold', [0, 0])
    pool = rule.get('pool') or []
    prizes = [None if not pool or random.randrange(100) < rule.get('fail', 0) else tuple(random.choice(pool))
              for _ in range(rule.get('items', 1))]
    return random.randint(lo, hi), prizes


@handler(CLI_JACKPOT, register=False)
class JackpotRecv(GameRecv):

    @inject
    async def handle(self, db=Provide['database'], inventory_repository=Provide['inventory_repository']):
        buf = self.buf.require(9)
        card, field4, card_item = buf.read_uint8(), buf.read_uint32(), buf.read_uint32()
        print(f"[{self.conn.addr}] Jackpot carta={card} campo4={field4} item={card_item}")
        user_id = self.user_id()
        chest = await inventory_repository.get_chest(user_id)
        row = next((c for c in chest if int(c['Item']) == card_item and c['Volume'] > 0), None)
        if card > 3 or card_item != CARD_ITEM + card or row is None:
            return await self.conn.on_send(Packet.new(SRV_JACKPOT, rtc=REFUSED))

        gold, prizes = draw((self.conn.server.config.get('jackpot') or {}).get(card) or {})
        records = [record(KIND_GOLD, count=gold)]
        transaction = await db.transaction()
        try:
            if not await inventory_repository.chest_consume(user_id, row['No'], 1):
                raise RuntimeError(f"baú {row['No']} não consumiu")
            if gold and not await inventory_repository.update_money(user_id, gold):
                raise RuntimeError("gold não atualizou")
            for prize in prizes:
                if prize is None:
                    records.append(record(KIND_FAIL))
                    continue
                item, count = prize
                no = await inventory_repository.insert_chest(user_id, item, AcquisitionType.Gift, ExpireType.Infinite, None, count)
                records.append(record(KIND_ITEM, no, item, count))
            await transaction.commit()
        except Exception as e:
            await transaction.rollback()
            print(f"[{self.conn.addr}] Jackpot falhou: {e}")
            return await self.conn.on_send(Packet.new(SRV_JACKPOT, rtc=REFUSED))
        await self.conn.on_send(jackpot_ok(card_item, row['Volume'] - 1, records))
        if gold:
            await self.conn.on_send(GoldResp.success(await inventory_repository.get_money(user_id)))


BOMB_COST = {1: 12, 2: 15}


@handler(CLI_JACKPOT_BOMB, register=False)
class JackpotBombRecv(GameRecv):

    @inject
    async def handle(self, db=Provide['database'], inventory_repository=Provide['inventory_repository']):
        refuse = Packet.new(SRV_JACKPOT_BOMB, rtc=REFUSED)
        buf = self.buf.require(9)
        card, no, card_item = buf.read_uint8(), buf.read_uint32(), buf.read_uint32()
        user_id = self.user_id()
        row = await inventory_repository.get_chest_item(user_id, no) if card in BOMB_COST else None
        cost = BOMB_COST.get(card, 0)
        if row is None or card_item != CARD_ITEM + card or int(row['Item']) != card_item or (row['Volume'] or 0) < cost:
            print(f"[{self.conn.addr}] Jackpot bomb recusado: carta={card} No={no} item={card_item}")
            return await self.conn.on_send(refuse)
        item, count = ((self.conn.server.config.get('jackpot_bomb') or {}).get(card) or [CARD_ITEM + card + 1, 1])
        transaction = await db.transaction()
        try:
            if not await inventory_repository.chest_consume(user_id, no, cost):
                raise RuntimeError(f"baú {no} não consumiu")
            prize_no = await inventory_repository.insert_chest(user_id, item, AcquisitionType.Gift, ExpireType.Infinite, None, count)
            await transaction.commit()
        except Exception as e:
            await transaction.rollback()
            print(f"[{self.conn.addr}] Jackpot bomb falhou: {e}")
            return await self.conn.on_send(refuse)
        await self.conn.on_send(Packet.new(SRV_JACKPOT_BOMB, rtc=0).u32(card_item).u8(row['Volume'] - cost)
                                .raw(record(KIND_ITEM, prize_no, item, count)))
