"""
Helpers compartilhados pelos handlers do GameServer.

- `Packet`: pacote S->C genérico com API fluente (u8/u16/u32/str...), sem precisar de uma classe por resposta.
- `EncryptedPacket`: mesmo formato de bloco do chat (u32 verificação + 12 bytes de dados), cifrado com a chave da sessão.
- `GameRecv` + `handler(...)`: base dos handlers C->S, com as guardas comuns (autenticado, no canal, na sala, mestre)
  feitas uma vez só, antes do `handle()`.
- `decrypt_blocks`: abre o corpo de um pacote C->S cifrado e valida o cabeçalho de cada bloco.

Este módulo não é importado automaticamente como handler (ver __init__.py, que pula base.py).
"""
from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryReader, BinaryWriter, PacketError
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection
    from gunbound.game.room import Room

CRYPT_MAGIC = 0x79CE9F82
BLOCK_DATA = 12
BLOCK_SIZE = 16


class Packet(BasePackageSend):
    """Pacote S->C. Ex.: `Packet.new(ServerPacket.SRV_ROOM_UPDATE, rtc=0)`."""

    def __init__(self, buf: BinaryWriter):
        self.buf = buf

    @classmethod
    def new(cls, cmd: int, rtc: int | None = None) -> 'Packet':
        buf = BinaryWriter()
        buf.write_uint16(int(cmd))
        if rtc is not None:
            buf.write_uint16(int(rtc))
        return cls(buf)

    # API fluente: cada método devolve o próprio pacote
    def u8(self, v) -> 'Packet':
        self.buf.write_uint8(int(v) & 0xFF); return self

    def u16(self, v) -> 'Packet':
        self.buf.write_uint16(int(v) & 0xFFFF); return self

    def u16be(self, v) -> 'Packet':
        self.buf.write_uint16(int(v) & 0xFFFF, le=False); return self

    def u32(self, v) -> 'Packet':
        self.buf.write_uint32(int(v) & 0xFFFFFFFF); return self

    def raw(self, data: bytes) -> 'Packet':
        self.buf.write_bytes(bytes(data)); return self

    def fixed(self, text: str, length: int) -> 'Packet':
        self.buf.write_string(text or '', length); return self

    def pstr(self, text: str) -> 'Packet':
        """String com prefixo de tamanho u8."""
        data = (text or '').encode('latin-1', errors='replace')[:255]
        self.buf.write_uint8(len(data)); self.buf.write_bytes(data); return self

    def text(self, text: str) -> 'Packet':
        """String sem tamanho até o fim do pacote (MOTD)."""
        self.buf.write_string(text or ''); return self

    def log_command(self, conn):
        reader = self.buf.to_reader()
        print(f"SEND>> [SS={conn.server.id:08X} SQ={reader.read_uint16(pos=2):04X} CD={reader.read_uint16(pos=4):04X}] {self.buf.to_hex(6)}")


class EncryptedPacket(Packet):
    """Corpo em blocos [u32 cmd-CRYPT_MAGIC][12 bytes], cifrado no envio (como o 0x201F)."""

    @classmethod
    def build(cls, cmd: int, plain: bytes) -> 'EncryptedPacket':
        pkt = cls.new(cmd)
        check = (int(cmd) - CRYPT_MAGIC) & 0xFFFFFFFF
        plain = plain or b'\x00'
        for i in range(0, len(plain), BLOCK_DATA):
            pkt.buf.write_uint32(check)
            pkt.buf.write_bytes(plain[i:i + BLOCK_DATA], BLOCK_DATA)
        return pkt

    def encrypt(self, conn):
        self.buf.write_bytes(conn.encrypt(self.buf.getvalue(6)), pos=6)

    def log_command(self, conn):
        reader = self.buf.to_reader()
        print(f"SEND>> [SS={conn.server.id:08X} SQ={reader.read_uint16(pos=2):04X} CD={reader.read_uint16(pos=4):04X}] (cifrado, {self.buf.size() - 6} bytes)")


def decrypt_blocks(conn: 'ClientConnection', data: bytes, cmd: int) -> BinaryReader:
    """
    Decifra um corpo C->S cifrado e devolve só os dados (12 bytes por bloco).
    O cabeçalho do bloco é `cmd + CRYPT_MAGIC` (o chat mostra que o cliente às vezes usa cmd+1; os dois são aceitos).
    """
    if not conn.get_derived_key():
        raise PacketError("pacote cifrado sem chave de sessão")
    if not data or len(data) % BLOCK_SIZE:
        raise PacketError(f"corpo cifrado com tamanho inválido ({len(data)})")
    plain = conn.decrypt(data)
    out = bytearray()
    for i in range(0, len(plain), BLOCK_SIZE):
        check = (int.from_bytes(plain[i:i + 4], 'little') + CRYPT_MAGIC) & 0xFFFFFFFF
        if check not in (cmd, cmd + 1):
            raise PacketError(f"bloco cifrado com verificação inválida {check:08X} (cmd {cmd:04X})")
        out += plain[i + 4:i + BLOCK_SIZE]
    return BinaryReader(bytes(out))


class GameRecv(BasePackageRecv):
    """
    Base dos handlers. Subclasses implementam `handle()`; as guardas declaradas em `handler(...)` rodam antes.
    Falha de guarda = pacote ignorado (o cliente original também não recebe resposta nesses casos).
    """
    command: ClassVar[int] = 0
    need_auth: ClassVar[bool] = True
    need_channel: ClassVar[bool] = False
    need_room: ClassVar[bool] = False
    need_master: ClassVar[bool] = False
    need_waiting: ClassVar[bool] = False
    need_in_game: ClassVar[bool] = False

    def __init__(self, conn: 'ClientConnection', buf: BinaryReader):
        self.conn = conn
        self.buf = buf

    @property
    def room(self) -> 'Room | None':
        return self.conn.room

    def user_id(self) -> str:
        return self.conn.data['profile']['Id']

    def allowed(self) -> bool:
        conn, room = self.conn, self.conn.room
        if self.need_auth and 'profile' not in conn.data:
            return False
        if self.need_channel and conn.channel is None:
            return False
        if (self.need_room or self.need_master or self.need_waiting or self.need_in_game) and room is None:
            return False
        if self.need_master and not room.is_master(conn):
            return False
        if self.need_waiting and not room.is_waiting():
            return False
        if self.need_in_game and room.is_waiting():
            return False
        return True

    async def process(self):
        if not self.allowed():
            print(f"[{self.conn.addr}] 0x{self.command:04X} recusado pelas guardas ({type(self).__name__})")
            return
        await self.handle()

    async def handle(self):
        raise NotImplementedError

    def log_command(self, conn):
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={self.command:04X}] {self.buf.to_hex(4)}")


def handler(cmd: int, *, auth=True, channel=False, room=False, master=False, waiting=False, in_game=False, register=True):
    """Declara as guardas e põe o handler no catálogo do TH. Ex.: `@handler(CLI_ROOM_KICK, master=True, waiting=True)`.
    register=False: handler de uma fase depois do TH, entra pelo add/replace da fase (gunbound/game/phase.py)."""
    def decorator(cls: type[GameRecv]):
        cls.command = int(cmd)
        cls.need_auth, cls.need_channel, cls.need_room = auth, channel, room
        cls.need_master, cls.need_waiting, cls.need_in_game = master, waiting, in_game
        return BasePackageFactory.register(int(cmd))(cls) if register else cls
    return decorator
