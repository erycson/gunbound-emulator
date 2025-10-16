from __future__ import annotations
from typing import TYPE_CHECKING
from gunbound.game.protocol import ClientPacket, ServerPacket
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.repository import UserRepository
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_USER_ID.value)
class UserIdRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn: 'ClientConnection', buf: BinaryReader):
        self.conn = conn
        self.buf = buf
        self.user_repository: UserRepository = UserRepository()

    async def process(self):
        # 0x0100 = ???? Quando envia presente o valor 1, eu chutaria q é a busca exata, pois a consulta se torna IN (nickname)
        # dando a entender, q já mais vai retornar mais de um resultado, mesmo tendo (LIMIT 100)
        # Também deixei 2 usuários com o mesmo nickname, e só retornou o primeiro, to chutando que é isso
        limit = self.buf.read_uint16()
        nickname = self.buf.read_string(12)
        if len(nickname) == 0:
            return
        
        users = await self.user_repository.find_by_nickname(nickname)
        users = users[:limit]

        await self.conn.on_send(UserIdResp.success(users))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_USER_ID.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class UserIdResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, users: list[dict[str, any]]):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_USER_ID)
        buf.write_uint16(len(users))

        for user in users:
            buf.write_string(user['Id'], 16)
            buf.write_string(user['Nickname'], 12)
        
        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")