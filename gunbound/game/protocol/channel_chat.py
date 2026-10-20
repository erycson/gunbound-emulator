from __future__ import annotations
from typing import TYPE_CHECKING
from typing_extensions import override
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util import BinaryWriter, BinaryReader
from gunbound.game import phase
from gunbound.game.protocol.enums import ClientPacket, ServerPacket
from gunbound.game.protocol.admin_console import forward_to_monitors
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_CHANNEL_CHAT.value)
class ChannelChatRecv(BasePackageRecv):

    def __init__(self, conn: 'ClientConnection', buf: BinaryReader):
        self.buf = buf
        self.conn = conn

    async def process(self):
        if not self.conn.get_derived_key():
            print(f"[{self.conn.id}] Chat no canal: Token ausente")
            return
        elif self.conn.channel is None:
            print(f"[{self.conn.id}] Chat no canal: Cliente não está em nenhum canal")
            return

        decrypted = self.conn.decrypt(self.buf.read_bytes())

        # A validação ocorre com os 4 primeiros bytes de cada bloco de 16 bytes, todos do mesmo jeito
        # Aqui estou validadando só o primeiro bloco
        command = (int.from_bytes(decrypted[:4], 'little', signed=False) + 0x79CE9F82) % 0xFFFFFFFF
        if command != 0x2011:
            print(f"[ChannelChatRecv] Comando inválido no pacote de chat do canal: {command:08X}, esperado: 2010")
            return

        # Extrai 12 bytes de cada bloco de 16 bytes, ignorando os 4 primeiros bytes de validação
        blocks = [decrypted[i + 4:i + 16] for i in range(0, len(decrypted), 16)]
        message_buf = BinaryReader(b''.join(blocks))
        length = message_buf.read_uint8()
        message = message_buf.read_string(length)

        await self.conn.channel.broadcast(ChannelChatResp.success(self.conn, message))
        await forward_to_monitors(self.conn, lambda: ChannelChatResp.success(self.conn, message))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_CHANNEL_CHAT.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class ChannelChatResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf

    @classmethod
    def success(cls, conn: 'ClientConnection', message: str):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_CHANNEL_CHAT)
        command = 0x201F - 0x79CE9F82
        position = conn.channel.get_client_position(conn)

        data = phase.of(conn).chat_body(position, conn.data['profile']['Nickname'], message)
        
        for i in range(0, len(data), 12):
            buf.write_int32(command)
            buf.write_bytes(data[i:i+12], 12)
            i += 12

        return cls(buf)

    @override
    def encrypt(self, conn):
        encrypted = conn.encrypt(self.buf.getvalue(6))
        self.buf.write_bytes(encrypted, pos=6)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex(8)}")