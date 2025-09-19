from gunbound.broker.protocol.base import BasePackageFactory
from gunbound.util.aes_cipher import AESCipher
from gunbound.util.binary_buffer import BinaryReader
from gunbound.util.dump import dump
from gunbound.broker.exceptions import UnknownPacketError

class ClientConnection:
    def __init__(self, reader, writer, crypto: AESCipher):
        self.reader = reader
        self.writer = writer
        self.crypto = crypto
        self.seq = 0

        ip, port = writer.get_extra_info('peername')
        self.addr = f"{ip}:{port}"

        print(f"[{self.addr}] Conexão estabelecida")

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()
        print(f"[{self.addr}] Conexão encerrada")

    def expected_checksum(self, packet_len: int) -> int:
        next = ( (self.seq + packet_len) & 0xFFFF )
        return (17405 * next - 24893) & 0xFFFF

    def advance_seq(self, packet_len: int) -> None:
        self.seq = (self.seq + packet_len) & 0xFFFFFFFF

    async def handler(self):
        try:
            while True:
                # Leia o cabeçalho inicial (2 bytes para o tamanho, little-endian)
                header = await self.reader.readexactly(2)
                if not header:
                    break  # conexão fechada
                packet_size = int.from_bytes(header, 'little', signed=False)

                # Ignore pacotes com tamanho inválido (ex: menor que header)
                if packet_size < 6:
                    if packet_size > 2:
                        await self.reader.readexactly(packet_size - 2)  # descarta o restante
                    continue
                
                # Leia o restante do pacote
                payload = await self.reader.readexactly(packet_size - 2)
                reader = BinaryReader(payload)
                with open("data.bin", "wb") as f:
                    f.write(reader.getvalue())
                await self.on_recv(packet_size, reader)
        finally:
            print(f"[{self.addr}] Fechando conexão")
            self.writer.close()
            await self.writer.wait_closed()

    async def on_recv(self, packet_size: int, buf: BinaryReader):
        try:
            checksum = buf.read_uint16()
            cmd = buf.read_uint16()

            # Valida o pacote
            expected = self.expected_checksum(packet_size)
            if checksum != expected:
                print(f"[{self.addr}] CHECKSUM FAIL< got={checksum:04X} exp={expected:04X} len={packet_size} cmd=0x{cmd:04X}")
                return

            # Processa o pacote
            print(f"[{self.addr}] RECV< SQ: {self.seq}, CMD: {cmd:#04x}, LEN: {packet_size}\n")
            self.advance_seq(packet_size)
            await BasePackageFactory.from_data(cmd, self, buf)
        except UnknownPacketError as e:
            cmd = e.getcmd()
            print(f"[{self.addr}] UnknownPacketError command: {cmd:#04x}. Dump: \n")
            dump(e.buf.getvalue())
