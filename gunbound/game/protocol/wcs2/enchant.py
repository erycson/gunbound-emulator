"""
Encantamento (XPEnchantDlg / CPopup_JewelEnchant) do cliente v584.

Pedidos (corpo depois do opcode; montados em 0x5337e5..0x533a48):
  0x7115 / 0x7410: u16 n = joias + 1 ([dlg+0x77e]+1; 0x77e conta os slots marcados, 0x530ea1/0x530ec1),
                   u32 No do item no baú [dlg+0x608], u32 item ([dlg+0x8c] avatar ou [dlg+0x31c] baú),
                   n-1 pares u32 No, u32 item de cada joia marcada (entrada local +4/+8). Joias: 0xAAE86..0xAAE8A,
                   uma por slot (0x53367e). 0x7410 se o item estiver em 0xC3502..0xC3569 (0x5338ec), senão 0x7115.
  0x7134: u16 ([dlg+0x77e]+1), u32 [dlg+0x608], u32 [dlg+0x8c], u32, u32 ([dlg+0x7b0][dlg+0x7c4]).
  0x6117: u8 [popup+0xa0] (0x51eb43).
Respostas: 0x7116 -> FUN_00533a60: u16 RTC, u8 código, u16 nível novo (o cliente grava no item em 0x532f40 e tira
           1 de cada joia marcada). 0x7411 -> FUN_00533bd0 (u8 código, u32 No, u32 item), 0x7135 -> FUN_00533ee0.
           RTC != 0 = "Erro no encantamento." (código 99). 0x6118 (0x4d8ef4): RTC == 0 recarrega e abre popup 0x81.
Códigos (FUN_00531480, textos do v584): 0 sucesso "+1", 1 falhou sem mudança, 2..4 caiu código-1 níveis, 5 destruído.
O nível de cada item vai no 0x6001 (phase.WCS2.chest_tail) e fica na tabela ChestEnchant; chances em EnchantLevel (seed).

0x7410 usa as mesmas regras do 0x7115.

0x7134 (selo de avatar): u16 1, u32 No do avatar, u32 código do avatar, u32 No do selo, u32 código do selo.
    Selo = decimal de até 8 dígitos lido em pares "A D" (0x4408c0): atributo A 1..8 (Delay, Pit, Attack, Defense,
    Energy, Item Delay, Shield, Popularity) ganha D+1. Itens 700124..700147: A = (código-700121)/3, bônus 3/6/9 pelo resto
    (do nome do item; o cliente não sabe). 700148 = Reset Seal (valor 0). Regras do cliente (0x534490): até 4 pares,
    atributo repetido não; reset só com selo. Avatar 0x40001..0x47fff não aceita selo (0x435460).
    0x7135 (0x533ee0): u16 RTC, u8 código (0 sucesso), u32 valor final (o cliente grava sempre no item: mandar o valor
    completo). Com RTC 0 o cliente tira 10 do contador do selo (+0x1c); aqui sai min(10, Volume) do banco.

0x6117 (CPopup_JewelEnchant, envio 0x51eb3b): u8 índice da receita. Receitas do JewelEnchantList.dat do cliente (texto,
    uma por linha, sscanf "%d %d %d %c %d %d %d %d %d %d %d" em 0x51e7d0): id, item produzido, ?, ?, custo em
    Emerald (0xAAEB1), Ruby (0xAAEB2), Diamond (0xAAEB3), requisito 1 (tipo, valor), requisito 2 (tipo, valor).
    Requisito (0x51eea0): 0 nenhum, 1 gold >= valor, 10-14/20-24/31-33/40/50-52 ter o item `valor`, 60-64 contadores do
    cliente (aqui aceitos). O cliente não confere nada antes de mandar e já tira 1 de cada joia com custo > 0 (uma vez,
    seja qual for o custo) e não desfaz se vier erro.
    0x6118 (0x4d8ef4): RTC != 0 = nada; RTC 0 -> leitor do 0x7131 (0x4361f0): u16 n + n x (u32 No, u32 item, u8 vestido,
    u8 aquisição, u8+[u32 segundos], u8+[u32 volume], u8+[u32]), sem o rabo do v584; o cliente só insere linhas novas,
    pede gold/cash (0x6104/0x6100) e abre a mensagem 0x81.
    Receitas: config `jewel_enchant` (listas na ordem das colunas do .dat; o índice é a linha). Os valores reais estão
    só no xfs; DEFAULT_JEWEL_RECIPES é nosso (custos de 1 para o baú do cliente não desalinhar). Requisitos são
    conferidos, não gastos.
Joias (ex3.dat do v584), cada uma vale uma vez por tentativa:
  Spirit (alma)       +EnchantLevel.JewelBonus % de sucesso, tirado da falha simples
  Nihility (topázio)  corta pela metade as chances de cair nível
  Nirvana             corta pela metade a chance de destruir
  Fortune Stone       sucesso certo ("evolução certeira", texto do cliente)
  Shield Stone        nunca destrói ("previne a demolição", texto do cliente)
shortcut: os papéis de Spirit/Nihility/Nirvana e as chances de queda/destruição são inventados (nenhuma fonte: cliente,
S2, S3 ofuscado, internet); só Success vem do S3 e Fortune/Shield do texto do cliente.
"""
import random
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import AcquisitionType, ExpireType
from gunbound.game.protocol.base import GameRecv, Packet, handler

CLI_ENCHANT, SRV_ENCHANT = 0x7115, 0x7116
CLI_ENCHANT_C35, SRV_ENCHANT_C35 = 0x7410, 0x7411
CLI_ENCHANT_CONFIRM, SRV_ENCHANT_CONFIRM = 0x7134, 0x7135
CLI_JEWEL_ENCHANT, SRV_JEWEL_ENCHANT = 0x6117, 0x6118
REFUSED = 1  # qualquer valor != 0 serve: o cliente só testa RTC != 0
JEWEL, JEWEL_SLOTS = 0xAAE86, 5
SPIRIT, NIHILITY, NIRVANA, FORTUNE, SHIELD = range(JEWEL, JEWEL + JEWEL_SLOTS)
SUCCESS, FAIL, DOWN1, DESTROY = 0, 1, 2, 5
GEMS = (0xAAEB1, 0xAAEB2, 0xAAEB3)  # Emerald, Ruby, Diamond
REQ_GOLD = 1
REQ_ITEM = frozenset({10, 11, 12, 13, 14, 20, 21, 22, 23, 24, 31, 32, 33, 40, 50, 51, 52})
REQ_CLIENT = frozenset(range(60, 65))
# [id, produto, ?, ?, Emerald, Ruby, Diamond, req1 tipo, req1 valor, req2 tipo, req2 valor]
DEFAULT_JEWEL_RECIPES = [
    [1, SPIRIT, 1, 'N', 1, 0, 0, 0, 0, 0, 0],
    [2, NIHILITY, 1, 'N', 0, 1, 0, 0, 0, 0, 0],
    [3, NIRVANA, 1, 'N', 0, 0, 1, 0, 0, 0, 0],
    [4, FORTUNE, 1, 'N', 1, 1, 1, REQ_GOLD, 10000, 0, 0],
    [5, SHIELD, 1, 'N', 0, 1, 1, REQ_GOLD, 5000, 0, 0],
]


def requirement_ok(kind: int, value: int, gold: int, owned: set) -> bool:
    if kind == 0 or kind in REQ_CLIENT:
        return True
    if kind == REQ_GOLD:
        return gold >= value
    return kind in REQ_ITEM and value in owned


def outcome(rate: dict, items: set, r: float) -> int:
    """Código do resultado para r em [0, 100) com as joias usadas (papéis no topo do arquivo). O que sobra é falha."""
    if FORTUNE in items:
        return SUCCESS
    down = 0.5 if NIHILITY in items else 1
    bands = [(SUCCESS, rate['Success'] + (rate['JewelBonus'] if SPIRIT in items else 0)),
             (DOWN1, rate['Down1'] * down), (DOWN1 + 1, rate['Down2'] * down), (DOWN1 + 2, rate['Down3'] * down),
             (DESTROY, 0 if SHIELD in items else rate['Destroy'] * (0.5 if NIRVANA in items else 1))]
    edge = 0
    for code, chance in bands:
        edge += chance
        if r < edge:
            return code
    return FAIL


@handler(CLI_ENCHANT, register=False)
class EnchantRecv(GameRecv):
    reply = SRV_ENCHANT

    def ok(self, code: int, chest_no: int, item: int, level: int) -> Packet:
        return Packet.new(self.reply, rtc=0).u8(code).u16(level)

    @inject
    async def handle(self, db=Provide['database'], inventory_repository=Provide['inventory_repository']):
        refuse = Packet.new(self.reply, rtc=REFUSED)
        buf = self.buf.require(10)
        n, chest_no, item = buf.read_uint16(), buf.read_uint32(), buf.read_uint32()
        if not 2 <= n <= JEWEL_SLOTS + 1:
            return await self.conn.on_send(refuse)
        buf.require(8 * (n - 1))
        pairs = [(buf.read_uint32(), buf.read_uint32()) for _ in range(n - 1)]
        user_id = self.user_id()
        chest = {int(c['No']): c for c in await inventory_repository.get_chest(user_id)}
        row = chest.get(chest_no)
        jewels = [chest.get(no) for no, _ in pairs]
        ok = (row is not None and int(row['Item']) == item and not JEWEL <= item < JEWEL + JEWEL_SLOTS
              and len({no for no, _ in pairs}) == len(pairs) == len({it for _, it in pairs})
              and all(j is not None and int(j['Item']) == it and JEWEL <= it < JEWEL + JEWEL_SLOTS and (j['Volume'] or 0) > 0
                      for j, (_, it) in zip(jewels, pairs)))
        level = int(row['EnchantLevel'] or 0) if ok else 0
        rate = await inventory_repository.get_enchant_rate(level + 1) if ok else None
        if rate is None:  # dono/joia errados ou nível máximo
            print(f"[{self.conn.addr}] Encantamento recusado: item={chest_no}/{item} joias={pairs}")
            return await self.conn.on_send(refuse)

        code = outcome(rate, {it for _, it in pairs}, random.random() * 100)
        new_level = {SUCCESS: level + 1, FAIL: level, DESTROY: 0}.get(code, max(0, level - (code - 1)))  # 2..4 cai code-1
        transaction = await db.transaction()
        try:
            for no, _ in pairs:
                if not await inventory_repository.chest_consume(user_id, no, 1):
                    raise RuntimeError(f"joia {no} não consumiu")
            if code == DESTROY:
                if not await inventory_repository.delete_chest(user_id, chest_no):
                    raise RuntimeError(f"item {chest_no} não apagou")
            elif new_level != level:
                await inventory_repository.set_enchant_level(chest_no, new_level)
            await transaction.commit()
        except Exception as e:
            await transaction.rollback()
            print(f"[{self.conn.addr}] Encantamento falhou: {e}")
            return await self.conn.on_send(refuse)
        worn = self.conn.data.get('avatar_enchant')
        if worn is not None and item in worn:  # vestido: a sala passa a mostrar o nível novo
            worn[item] = (new_level, worn[item][1])
        print(f"[{self.conn.addr}] Encantamento item={chest_no} nível {level} -> {new_level} (código {code}, {len(pairs)} joias)")
        await self.conn.on_send(self.ok(code, chest_no, item, new_level))


@handler(CLI_ENCHANT_C35, register=False)
class EnchantC35Recv(EnchantRecv):
    """0x7410 (cartas de mobile 800002..800105): mesmas regras do 0x7115. 0x7411 (0x533bd0): u16 RTC, u8 código,
    u32 No, u32 item, i16 nível. O item nunca muda aqui, então o No e o item voltam iguais (mudar o item sem trocar o No
    faz o cliente sair em 0x533e34). As joias o cliente sempre tira sozinho."""
    reply = SRV_ENCHANT_C35

    def ok(self, code, chest_no, item, level):
        return Packet.new(self.reply, rtc=0).u8(code).u32(chest_no).u32(item).u16(level)


SEAL_FIRST, SEAL_RESET = 700124, 700148
SEAL_USE = 10
NO_SEAL_AVATAR = range(0x40001, 0x48000)


def new_seal(old: int, seal_item: int) -> int | None:
    """Valor do selo depois de usar `seal_item`, ou None se o cliente também recusaria."""
    if seal_item == SEAL_RESET:
        return 0 if old else None
    if not SEAL_FIRST <= seal_item < SEAL_RESET:
        return None
    attr, bonus = (seal_item - SEAL_FIRST) // 3 + 1, ((seal_item - SEAL_FIRST) % 3 + 1) * 3
    digits = str(old) if old else ''
    if len(digits) >= 8 or str(attr) in digits[::2]:
        return None
    return old * 100 + attr * 10 + bonus - 1


assert new_seal(0, 700124) == 12 and new_seal(12, 700129) == 1228 and new_seal(1228, 700125) is None
assert new_seal(12345678, 700140) is None and new_seal(0, SEAL_RESET) is None and new_seal(12, SEAL_RESET) == 0


@handler(CLI_ENCHANT_CONFIRM, register=False)
class EnchantConfirmRecv(GameRecv):
    @inject
    async def handle(self, inventory_repository=Provide['inventory_repository']):
        buf = self.buf.require(18)
        buf.read_uint16()
        avatar_no, avatar_item, seal_no, seal_item = (buf.read_uint32() for _ in range(4))
        user_id = self.user_id()
        chest = {int(c['No']): c for c in await inventory_repository.get_chest(user_id)}
        avatar, seal = chest.get(avatar_no), chest.get(seal_no)
        ok = (avatar is not None and seal is not None and int(avatar['Item']) == avatar_item
              and avatar_item not in NO_SEAL_AVATAR and int(seal['Item']) == seal_item and (seal['Volume'] or 0) > 0)
        value = new_seal(int(avatar.get('Seal') or 0), seal_item) if ok else None
        if value is None:
            print(f"[{self.conn.addr}] Selo recusado: avatar={avatar_no}/{avatar_item} selo={seal_no}/{seal_item}")
            return await self.conn.on_send(Packet.new(SRV_ENCHANT_CONFIRM, rtc=REFUSED))
        if not await inventory_repository.chest_consume(user_id, seal_no, min(SEAL_USE, int(seal['Volume']))):
            return await self.conn.on_send(Packet.new(SRV_ENCHANT_CONFIRM, rtc=REFUSED))
        await inventory_repository.set_seal(avatar_no, value)
        worn = self.conn.data.get('avatar_enchant')
        if worn is not None and avatar_item in worn:
            worn[avatar_item] = (worn[avatar_item][0], value)
        print(f"[{self.conn.addr}] Selo avatar={avatar_no} -> {value}")
        await self.conn.on_send(Packet.new(SRV_ENCHANT_CONFIRM, rtc=0).u8(SUCCESS).u32(value))


@handler(CLI_JEWEL_ENCHANT, register=False)
class JewelEnchantRecv(GameRecv):
    @inject
    async def handle(self, db=Provide['database'], inventory_repository=Provide['inventory_repository']):
        index = self.buf.require(1).read_uint8()
        recipes = self.conn.server.config.get('jewel_enchant') or DEFAULT_JEWEL_RECIPES
        user_id = self.user_id()
        chest = await inventory_repository.get_chest(user_id)
        recipe = recipes[index] if index < len(recipes) else None
        if recipe is None or not self.can_craft(recipe, chest, await inventory_repository.get_money(user_id)):
            print(f"[{self.conn.addr}] 0x6117 recusado: receita {index}")
            return await self.conn.on_send(Packet.new(SRV_JEWEL_ENCHANT, rtc=REFUSED))
        product, costs = int(recipe[1]), [int(c) for c in recipe[4:7]]
        transaction = await db.transaction()
        try:
            for gem, cost in zip(GEMS, costs):
                for row in (r for r in chest if int(r['Item']) == gem and (r['Volume'] or 0) > 0):
                    take = min(cost, int(row['Volume']))
                    if take and not await inventory_repository.chest_consume(user_id, row['No'], take):
                        raise RuntimeError(f"joia {row['No']} não consumiu")
                    cost -= take
            chest_no = await inventory_repository.insert_chest(user_id, product, AcquisitionType.Gift, ExpireType.Infinite, None, 1)
            await transaction.commit()
        except Exception as e:
            await transaction.rollback()
            print(f"[{self.conn.addr}] 0x6117 falhou: {e}")
            return await self.conn.on_send(Packet.new(SRV_JEWEL_ENCHANT, rtc=REFUSED))
        print(f"[{self.conn.addr}] Jóia: receita {index} -> item {product} (No {chest_no}), custos {costs}")
        await self.conn.on_send(Packet.new(SRV_JEWEL_ENCHANT, rtc=0).u16(1).u32(chest_no).u32(product)
                                .u8(0).u8(ord(AcquisitionType.Gift.value)).u8(0).u8(1).u32(1).u8(1).u32(0))

    @staticmethod
    def can_craft(recipe, chest, gold) -> bool:
        volume = {}
        for r in chest:
            volume[int(r['Item'])] = volume.get(int(r['Item']), 0) + int(r['Volume'] or 0)
        owned = {item for item, v in volume.items() if v > 0}
        costs = [int(c) for c in recipe[4:7]]
        return (all(volume.get(gem, 0) >= cost for gem, cost in zip(GEMS, costs))
                and requirement_ok(int(recipe[7]), int(recipe[8]), gold, owned)
                and requirement_ok(int(recipe[9]), int(recipe[10]), gold, owned))
