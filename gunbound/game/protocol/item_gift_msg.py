"""
0x6004 (vazio) -> um 0x6005 por presente pendente, sem RTC (servidor original 0x42e140 e leitores TH 0x4118b9,
v440 0x411017, v584 0x41256b; nenhum deles lê resposta ao 0x6004):
    u32 MenuId, u32 GiftItemNo (chave que volta no 0x6008), u8 período, remetente12, u32 time_t, u8 len, texto.
O período é o índice do texto 500020+n do cliente (tabela do original pelo ExpireType). O len não é conferido pelo
cliente: mais de 0x83 bytes estoura o registro, então corta em 0x82.

0x6032 (sem RTC; servidor 2006 0x42e398, 2007 0x434bb0; clientes v440 0x4118a6 e v584 0x412587): aviso a quem deu o
presente, mandado só aqui, nas linhas A/D (aceito/recusado) do GiftMsg; depois o original apaga essas linhas no mesmo
job (0x41f093), então cada aviso sai uma vez. Corpo: Id12 de quem respondeu (o 0x6008 troca Sender/Receiver), u32 MenuId,
u8 período (W 0, M 1, Y 2; o original manda lixo nos outros), u8 1 = aceito / 0 = recusado. O v440 mostra o diálogo
(textos 500027/500028); o v584 só enfileira e não mostra. O original só envia linhas com MenuId e GiftItemNo != 0.
"""
from __future__ import annotations
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import GiftMsgType
from gunbound.game.protocol.base import GameRecv, Packet, handler
from gunbound.game.protocol.enums import ClientPacket

SRV_GIFT = 0x6005
SRV_GIFT_ANSWER = 0x6032
ANSWER_PERIOD = {'W': 0, 'M': 1, 'Y': 2}
GIFT_TEXT_MAX = 0x82
GIFT_PERIOD = {'3': 0, 'W': 1, 'T': 2, 'M': 3, 'F': 4, 'H': 5, 'Y': 6, 'I': 7}  # original 0x42e340


def gift_packet(msg: dict) -> Packet:
    text = (msg['Msg'] or '').encode('latin-1', 'replace')[:GIFT_TEXT_MAX]
    return (Packet.new(SRV_GIFT).u32(msg['MenuId']).u32(msg['GiftItemNo'] or 0).u8(GIFT_PERIOD.get(msg['ExpireType'], 1))
            .fixed(msg['Sender'], 12).u32(int(msg['SentTime'].timestamp())).u8(len(text)).raw(text))


def answer_packet(msg: dict) -> Packet:
    return (Packet.new(SRV_GIFT_ANSWER).fixed(msg['Sender'], 12).u32(msg['MenuId'])
            .u8(ANSWER_PERIOD.get(msg['ExpireType'], 0)).u8(1 if msg['MsgType'] == GiftMsgType.Accepted else 0))


@handler(ClientPacket.CLI_ITEM_GIFT_MSG)
class ItemGiftMsgRecv(GameRecv):
    @inject
    async def handle(self, user_repository=Provide['user_repository']):
        answered = []
        for msg in await user_repository.get_gift_msgs(self.user_id()):
            if msg['MsgType'] == GiftMsgType.Gift:
                if msg['MenuId'] and msg['GiftItemNo']:
                    await self.conn.on_send(gift_packet(msg))
            elif msg['MsgType'] in (GiftMsgType.Accepted, GiftMsgType.Denied):
                if msg['MenuId'] and msg['GiftItemNo']:
                    await self.conn.on_send(answer_packet(msg))
                answered.append(msg['No'])  # o original apaga mesmo as que não mandou
        if answered:
            await user_repository.delete_gift_msgs(answered)
