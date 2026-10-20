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

0x7410 usa as mesmas regras do 0x7115. shortcut: 0x7134 (selos de avatar, valor em pares de dígitos por atributo) e 0x6117
(receitas do JewelEnchantList.dat, dentro do xfs) continuam recusando (RTC != 0).
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
from gunbound.game.protocol.base import GameRecv, Packet, handler

CLI_ENCHANT, SRV_ENCHANT = 0x7115, 0x7116
CLI_ENCHANT_C35, SRV_ENCHANT_C35 = 0x7410, 0x7411
CLI_ENCHANT_CONFIRM, SRV_ENCHANT_CONFIRM = 0x7134, 0x7135
CLI_JEWEL_ENCHANT, SRV_JEWEL_ENCHANT = 0x6117, 0x6118
REFUSED = 1  # qualquer valor != 0 serve: o cliente só testa RTC != 0
JEWEL, JEWEL_SLOTS = 0xAAE86, 5
SPIRIT, NIHILITY, NIRVANA, FORTUNE, SHIELD = range(JEWEL, JEWEL + JEWEL_SLOTS)
SUCCESS, FAIL, DOWN1, DESTROY = 0, 1, 2, 5


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


class _Refuse(GameRecv):
    reply = 0

    async def handle(self):
        await self.conn.on_send(Packet.new(self.reply, rtc=REFUSED))


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


@handler(CLI_ENCHANT_CONFIRM, register=False)
class EnchantConfirmRecv(_Refuse):
    reply = SRV_ENCHANT_CONFIRM


@handler(CLI_JEWEL_ENCHANT, register=False)
class JewelEnchantRecv(_Refuse):
    reply = SRV_JEWEL_ENCHANT
