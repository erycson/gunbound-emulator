"""
Eventos do cliente v584 (WCS2). Só o que o cliente fixa; valores de regra de jogo vêm do config do game server.

Todos os pedidos abaixo têm corpo VAZIO (só cabeçalho, 0x4558c0/`mov [sock+0x94]` + fechamento 0x455ae0).
Respostas lidas no handler global 0x40f740. Sem chave no config = não responde: o cliente só age com RTC 0,
então ficar quieto é o mesmo que recusar (nenhum desses pedidos trava tela esperando resposta).

- 0x7012 (0x5148cf, enviado no 0x1012 ok junto com 0x6000/0x6004) -> 0x7013: u16 RTC; RTC 0 -> u32 em
  global+0x688a4 (0x41393e) = lições do tutorial liberadas (0..9, XPTutorialSelectDlg 0x585647). Responde sempre com o
  progresso salvo (Game.EventScore3); `event_7013_value` no config sobrescreve.
- 0x6108 (0x433116, seguido de 0x6104) -> 0x6109: u16 RTC; RTC 0 -> u32 no valor protegido global+0x1b838
  (0x4131a0), o mesmo do 1º u32 do 0x1013 (0x40f8dd). Servidor 2007 (SVC_GP -> GDBIN_GP 0x41eafd):
  `SELECT totalscore FROM game WHERE id` e responde sempre u16 0 + u32 TotalScore.
- 0x6106 (0x432fd4, XPReadyEventDlg) -> 0x6107: u16 RTC; RTC 0 -> u16 gravado em global+0x68118[idx] e passado
  ao XPReadyEventDlg (FUN_00550000). Config `event_6107_id`.

Tutorial (o 0x91f980 do cliente é a cena atual; 0x6889c = passo do tutorial):
- 0x7014 (0x58517d, fim do tutorial): u32 lição+1 (9 lições, 0..8). O servidor grava max(progresso, lição+1) e, na 1ª vez,
  paga o prêmio de config['tutorial'] (TutorialEndRecv). O 0x7015 (0x413753) NÃO lê corpo nem RTC: compara 0x688a4 com 0x6889c,
  fecha o diálogo da cena (0xb/6/4) e muda de cena (0x41cd40). Sem ele a tela do tutorial não volta.
- 0x3433 (0x559953, carregamento da partida, host depois da contagem e do 0x8600 local): corpo vazio, o cliente não espera
  resposta (segue sozinho). Só silencia o "sem handler".
"""
import random
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import AcquisitionType, ExpireType, MessageType
from gunbound.game import phase
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.gold import GoldResp
from gunbound.game.protocol.item import ItemResp

CLI_EVENT_7012, SRV_EVENT_7013 = 0x7012, 0x7013
CLI_EVENT_6108, SRV_EVENT_6109 = 0x6108, 0x6109
CLI_READY_EVENT, SRV_READY_EVENT = 0x6106, 0x6107
TUTORIAL_LESSONS = 9


class _ConfigReply(GameRecv):
    reply: int = 0
    key: str = ''
    width: int = 4  # bytes do valor depois do RTC

    async def handle(self):
        value = self.conn.server.config.get(self.key)
        if value is None:
            return  # sem valor configurado: não responde (cliente ignora RTC != 0)
        pkt = Packet.new(self.reply, rtc=0)
        await self.conn.on_send(pkt.u32(value) if self.width == 4 else pkt.u16(value))


@handler(CLI_EVENT_7012, register=False)
class Event7012Recv(GameRecv):
    @inject
    async def handle(self, user_repository=Provide['user_repository']):
        value = self.conn.server.config.get('event_7013_value')
        if value is None:
            value = (self.conn.data.get('game') or {}).get('EventScore3') or 0
        await self.conn.on_send(Packet.new(SRV_EVENT_7013, rtc=0).u32(min(int(value), TUTORIAL_LESSONS)))
        # fichas do caça-níquel: o 0x7113 é push sem pedido; o 0x7012 sai uma vez no login (0x5148cf)
        from gunbound.game.protocol.wcs2.slot_machine import tokens_packet
        await self.conn.on_send(tokens_packet((self.conn.data.get('game') or {}).get('EventScore2') or 0))
        # saldo da Rena (0x7123): sem ele o botão do XPRenaDlg nunca habilita
        from gunbound.game.protocol.wcs2.shop import rena_points_packet
        await self.conn.on_send(rena_points_packet(await user_repository.get_points(self.user_id(), 'RenaPoints')))


@handler(CLI_EVENT_6108, register=False)
class Event6108Recv(GameRecv):
    @inject
    async def handle(self, user_repository=Provide['user_repository']):
        score = await user_repository.get_points(self.user_id(), 'TotalScore')
        await self.conn.on_send(Packet.new(SRV_EVENT_6109, rtc=0).u32(score & 0xFFFFFFFF))


@handler(CLI_READY_EVENT, register=False)
class ReadyEventRecv(_ConfigReply):
    reply, key, width = SRV_READY_EVENT, 'event_6107_id', 2


def avatar_range(slot: str, gender: int) -> tuple[int, int]:
    """Faixa de código do avatar por tipo (head/body/flag) e sexo (0 masc, 1 fem), dos .dat do avatar.xfs do v584:
    mb 0x8000.., fb 0.., mh 0x18000.., fh 0x10000.., mf 0x38000.. (bandeira, sem versão feminina)."""
    if slot == 'flag':
        return 0x38000, 0x40000
    base = {'body': 0, 'head': 0x10000}[slot] + (0 if gender else 0x8000)
    return base, base + 0x8000


@handler(0x7014, register=False)
class TutorialEndRecv(GameRecv):
    """Prêmio na 1ª conclusão de cada lição, de config['tutorial'][lição] (o cliente só mostra o texto, Language.txt
    2000552..2000576, e o ícone, tabela fixa em 0x422c45; nenhum servidor original que temos trata o 0x7014).
    gold vai direto; items [[código, qtd]] vão para o baú; avatar (head/body/flag) chega como presente (GiftMsg),
    sorteado entre os `avatar_pool` menus mais baratos em gold daquele tipo e sexo."""

    @inject
    async def handle(self, db=Provide['database'], user_repository=Provide['user_repository'],
                     inventory_repository=Provide['inventory_repository']):
        lesson = self.buf.require(4).read_uint32()
        game = self.conn.data.get('game') or {}
        first = 1 <= lesson <= TUTORIAL_LESSONS and lesson > (game.get('EventScore3') or 0)
        config = self.conn.server.config.get('tutorial') or {}
        rule = (config.get(lesson) or {}) if first else {}
        user_id = self.user_id()
        if first:
            transaction = await db.transaction()
            try:
                await user_repository.set_tutorial(user_id, lesson)
                if rule.get('gold') and not await inventory_repository.update_money(user_id, rule['gold']):
                    raise RuntimeError("gold não atualizou")
                for item, count in rule.get('items') or []:
                    await inventory_repository.insert_chest(user_id, item, AcquisitionType.Gift, ExpireType.Infinite, None, count)
                if rule.get('avatar'):
                    lo, hi = avatar_range(rule['avatar'], int(self.conn.data['profile']['Gender']))
                    menus = await inventory_repository.cheapest_menus(lo, hi, config.get('avatar_pool', 10))
                    if menus:
                        menu, sender = random.choice(menus), config.get('sender', 'GunBound')
                        gift = await inventory_repository.insert_giftitem(sender, user_id, menu, AcquisitionType.Gift)
                        await inventory_repository.insert_giftmsg(sender, user_id, menu, gift, MessageType.Gift,
                                                                  f"Premio da licao {lesson}", ExpireType.Infinite)
                await transaction.commit()
            except Exception as e:
                await transaction.rollback()
                print(f"[{self.conn.addr}] Prêmio da lição {lesson} falhou: {e}")
                rule, first = {}, False
            if first:
                game['EventScore3'] = lesson  # próximo 0x7012 na mesma sessão já vê
                print(f"[{self.conn.addr}] Lição {lesson} concluída, prêmio {rule}")
        await self.conn.on_send(Packet.new(0x7015, rtc=0))
        # resposta ao próprio 0x7014: atualiza gold e baú na tela, como o jackpot faz com o gold
        if rule.get('gold'):
            await self.conn.on_send(GoldResp.success(await inventory_repository.get_money(user_id)))
        if rule.get('items'):
            chest = await inventory_repository.get_chest(user_id)
            await self.conn.on_send(ItemResp.success(chest, phase.of(self.conn), self.conn.data.get('client_version', 0)))


@handler(0x3433, register=False)
class LoadingDoneRecv(GameRecv):
    async def handle(self):
        pass


@handler(0x1078, register=False)
class ErrorCodeOkRecv(GameRecv):
    """0x1078 (vazio, OK do ErrorCodeDialog 0x4d3820, aberto pelo 0x1060 de e-mail não verificado): 0x1079 RTC 0
    mostra o texto 270 ("instruções enviadas para seu e-mail"). O servidor nunca manda 0x1060, então é só a resposta."""

    async def handle(self):
        await self.conn.on_send(Packet.new(0x1079, rtc=0))


@handler(0x7130, register=False)
class EnchantChallengeEndRecv(GameRecv):
    """0x7130 (vazio, CPopup_Enchant_Challenge 0x51c0b0): fim do desafio; o cliente não tem 0x7131. Só registra."""

    async def handle(self):
        print(f"[{self.conn.addr}] 0x7130 fim do desafio de encantamento")


EVENTS = {c.command: c for c in (Event7012Recv, Event6108Recv, ReadyEventRecv, TutorialEndRecv, LoadingDoneRecv, ErrorCodeOkRecv, EnchantChallengeEndRecv)}
