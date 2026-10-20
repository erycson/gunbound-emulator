"""
Caça-níquel (XPSlotMachineDlg) do cliente v584.

Pedido 0x7110 (0x579bbe): u8 moeda (escolha/3: 0 fichas, 1 cash), u8 aposta (escolha%3).
    Custos fixos no cliente (0x57a940): fichas 10/50/100, cash 500/1000/1500; sem saldo o cliente nem manda.
Resposta 0x7111 (0x413aa8, só com o diálogo esperando; 10 s sem resposta = falha local):
    u16 RTC; RTC != 0 -> resultado 4 sem débito. RTC 0 -> u8 resultado, u32 valor, e o cliente debita o custo sozinho.
    Resultados: 0 fichas += valor (texto 8002), 1 gold += valor (8003), 2/3 item = valor (só mostra o nome, 8004),
    4 perdeu (8005).
0x7113 (push, 0x413c2b): u16 RTC 0 + u32 fichas. Vai junto da resposta do 0x7012 (login) e depois de cada giro.

Prêmios: regra do servidor. Chave de config `slot_machine`: lista de [resultado, valor, peso] onde o valor é multiplicado
pela aposta (1, 2, 3); padrão em DEFAULT_TABLE. shortcut: prêmios de item (2/3) não são suportados.
Fichas guardadas em Game.EventScore2 (user_repository.add_slot_tokens).
"""
import random
from dependency_injector.wiring import Provide, inject
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.cash import CashResp
from gunbound.game.protocol.gold import GoldResp

CLI_SLOT_MACHINE, SRV_SLOT_MACHINE, SRV_SLOT_TOKENS = 0x7110, 0x7111, 0x7113
TOKENS, CASH = 0, 1
COST = {TOKENS: (10, 50, 100), CASH: (500, 1000, 1500)}
WIN_TOKENS, WIN_GOLD, LOSE = 0, 1, 4
DEFAULT_TABLE = [[LOSE, 0, 60], [WIN_TOKENS, 20, 25], [WIN_GOLD, 500, 12], [WIN_GOLD, 3000, 3]]
REFUSED = 1


def tokens_packet(tokens: int) -> Packet:
    return Packet.new(SRV_SLOT_TOKENS, rtc=0).u32(tokens)


def spin(table, rng=random) -> tuple[int, int]:
    result, value, _ = rng.choices(table, weights=[w for *_, w in table])[0]
    return int(result), int(value)


@handler(CLI_SLOT_MACHINE, register=False)
class SlotMachineRecv(GameRecv):
    @inject
    async def handle(self, inventory_repository=Provide['inventory_repository'], user_repository=Provide['user_repository']):
        buf = self.buf.require(2)
        currency, bet = buf.read_uint8(), buf.read_uint8()
        user_id, game = self.user_id(), self.conn.data['game']
        if currency not in COST or bet > 2:
            return await self.conn.on_send(Packet.new(SRV_SLOT_MACHINE, rtc=REFUSED))
        cost = COST[currency][bet]
        paid = (await user_repository.add_slot_tokens(user_id, -cost) if currency == TOKENS
                else await inventory_repository.update_cash(user_id, -cost))
        if not paid:
            return await self.conn.on_send(Packet.new(SRV_SLOT_MACHINE, rtc=REFUSED))
        table = [r for r in (self.conn.server.config.get('slot_machine') or DEFAULT_TABLE) if int(r[0]) in (WIN_TOKENS, WIN_GOLD, LOSE)]
        result, value = spin(table)
        value *= bet + 1
        if result == WIN_TOKENS:
            await user_repository.add_slot_tokens(user_id, value)
        elif result == WIN_GOLD:
            await inventory_repository.update_money(user_id, value)
            game['Money'] = (game.get('Money') or 0) + value
        if currency == TOKENS:
            game['EventScore2'] = (game.get('EventScore2') or 0) - cost
        game['EventScore2'] = (game.get('EventScore2') or 0) + (value if result == WIN_TOKENS else 0)
        print(f"[{self.conn.addr}] Caça-níquel moeda={currency} aposta={bet}: resultado {result} valor {value}")
        await self.conn.on_send(Packet.new(SRV_SLOT_MACHINE, rtc=0).u8(result).u32(value))
        await self.conn.on_send(tokens_packet(game['EventScore2']))
        if currency == CASH:
            await self.conn.on_send(CashResp.success(await inventory_repository.get_cash(user_id)))
        if result == WIN_GOLD:
            await self.conn.on_send(GoldResp.success(await inventory_repository.get_money(user_id)))
