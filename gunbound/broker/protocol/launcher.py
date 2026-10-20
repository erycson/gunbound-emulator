"""Pacotes do NyxLauncher depois do login (0x1310 -> 0x1312).
Fluxo do launcher: 0x3000 -> 0x3001, depois 0x4000 -> 0x4001 (código 0 abre o jogo)."""
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.broker.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader


class LauncherResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf

    @classmethod
    def ok(cls, cmd: int, code: int = ServerCode.SRV_OK):
        # só cmd + código: com 8 bytes o launcher não abre popup no 0x3001 e não mostra horário no 0x4001
        buf = BinaryWriter()
        buf.write_uint16(cmd)
        buf.write_uint16(code)
        return cls(buf)

    def log_command(self, conn):
        reader = self.buf.to_reader()
        print(f"SEND>> [SS={conn.broker.id:08X} SQ={reader.read_uint16(pos=2):04X} CD={reader.read_uint16(pos=4):04X} RTC={reader.read_uint16(pos=6):04X}]")


@BasePackageFactory.register(ClientPacket.CLI_GET_MSG.value)
class GetMsgRecv(BasePackageRecv):
    def __init__(self, conn, buf: BinaryReader):
        self.conn = conn
        self.buf = buf

    async def process(self):
        await self.conn.on_send(LauncherResp.ok(ServerPacket.SRV_GET_MSG))

    def log_command(self, conn):
        print(f"RECV<< [SS={conn.broker.id:08X} CD={ClientPacket.CLI_GET_MSG.value:04X}] {self.buf.to_hex(4)}")


@BasePackageFactory.register(ClientPacket.CLI_START_GAME.value)
class StartGameRecv(BasePackageRecv):
    def __init__(self, conn, buf: BinaryReader):
        self.conn = conn
        self.buf = buf

    async def process(self):
        # só abre o jogo para a conexão que passou pelo login 0x1310 (código != 0 o launcher não abre)
        code = ServerCode.SRV_OK if self.conn.logged_in else ServerCode.SRV_ERR_NOT_AUTHORIZED
        await self.conn.on_send(LauncherResp.ok(ServerPacket.SRV_START_GAME, code))

    def log_command(self, conn):
        print(f"RECV<< [SS={conn.broker.id:08X} CD={ClientPacket.CLI_START_GAME.value:04X}] {self.buf.to_hex(4)}")
