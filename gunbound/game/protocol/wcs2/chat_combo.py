"""
Chat novo (XPChatComboBox) do cliente v584. Layouts lidos do GunBound.gme (VA = offset + 0x400000).

0x7500 C->S (envio em 0x529e10): corpo vazio, só sai quando a lista do cliente (0x92a614) está vazia.
0x7501 S->C (switch global 0x40f740, case em 0x414ce7; não está na lista cifrada de 0x455d6d):
    u16 ignorado (0x414cef pula 2 bytes), i16 n (0x414cf7), n x 16 bytes de texto (0x414d05..0x414d33;
    o cliente põe o 0 no 17o byte). n <= 0: lista fica vazia.
0x7502 S->C (case em 0x414963): u16 n + n x u32 em 0x68b64. É empurrado pelo servidor, não responde ao 0x7500;
    a origem dos u32 não está no cliente -> não implementado (pendente).

Conteúdo da lista é regra do servidor: chave de config `chat_combo_entries` (lista de strings, 16 bytes cada).
Sem a chave, responde n=0 (o cliente trata: 0x414cff pula o laço).
"""
from __future__ import annotations
from gunbound.game.protocol.base import GameRecv, Packet, handler

CLI_CHAT_COMBO_LIST = 0x7500
SRV_CHAT_COMBO_LIST = 0x7501
ENTRY_SIZE = 16


@handler(CLI_CHAT_COMBO_LIST, register=False)
class ChatComboListRecv(GameRecv):
    async def handle(self):
        entries = list(self.conn.server.config.get('chat_combo_entries') or [])[:0x7FFF]
        pkt = Packet.new(SRV_CHAT_COMBO_LIST).u16(0).u16(len(entries))
        for text in entries:
            pkt.fixed(str(text), ENTRY_SIZE)
        await self.conn.on_send(pkt)
