import datetime
from gunbound.game.client import ClientConnection
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.respository import UserRepository

@BasePackageFactory.register(ClientPacket.CLI_ITEM_GIFT_MSG.value)
class ItemGiftMsgRecv(BasePackageRecv):

    def __init__(self, conn: ClientConnection, buf: BinaryReader):
        self.conn = conn
        self.user_repository: UserRepository = UserRepository()

    async def process(self):
        gift_msgs = await self.user_repository.get_gift_msgs(self.conn.data['game']['Id'])
        if len(gift_msgs) > 0:
            await self.conn.on_send(ItemGiftMsgResp.success(gift_msgs))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ITEM_GIFT_MSG.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class ItemGiftMsgResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, gift_msgs):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM_GIFT_MSG)
        buf.write_uint16(ServerCode.SRV_OK)

        for msg in gift_msgs:
            time = datetime.strptime(msg['SentTime'], "%Y-%m-%d %H:%M:%S").timestamp()
            buf.write_uint32(msg['MenuId'])
            buf.write_uint32(msg['No'])
            buf.write_uint8(1) # Desconhecido, talvez diga se o presente é permanente ou temporário
            buf.write_string(msg['Sender'], 12)
            buf.write_uint32(int(time)) # Ingora os milisegundos
            buf.write_uint8(len(msg['Msg']))
            buf.write_string(msg['Msg'])

        return cls(buf)
    
    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)

        print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex()}")