from __future__ import annotations

from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.repository import UserRepository
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_ITEM_GIFT_MSG.value)
@inject
class ItemGiftMsgRecv(BasePackageRecv):
    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        user_repository: 'UserRepository' = Provide['user_repository'],
    ):
        self.buf = buf
        self.conn = conn
        self.user_repository = user_repository

    async def process(self):
        gift_msgs = await self.user_repository.get_gift_msgs(self.conn.data['profile']['Id'])
        if len(gift_msgs) > 0:
            await self.conn.on_send(ItemGiftMsgResp.success(gift_msgs))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ITEM_GIFT_MSG.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class ItemGiftMsgResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, gift_msgs):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM_GIFT_MSG)
        buf.write_uint16(ServerCode.SRV_OK)

        for msg in gift_msgs:
            time = msg['SentTime'].timestamp()
            buf.write_uint32(msg['MenuId'])
            buf.write_uint32(msg['No'])
            buf.write_uint8(1) # Desconhecido, talvez diga se o presente é permanente ou temporário
            buf.write_string(msg['Sender'], 12)
            buf.write_uint32(int(time)) # Ingora os milisegundos
            buf.write_uint8(len(msg['Msg']))
            buf.write_string(msg['Msg'])

        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")