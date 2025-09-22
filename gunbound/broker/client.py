from asyncio import IncompleteReadError
from gunbound.broker.protocol.base import BasePackageFactory
from gunbound.util.aes_cipher import AESCipher
from gunbound.util.binary_buffer import BinaryReader, BinaryWriter
from gunbound.util.dump import dump
from gunbound.broker.protocol.base import BasePackageSend
from gunbound.broker.exceptions import UnknownPacketError

class ClientConnection:
    def __init__(self, broker, reader, writer):
        self.id = id(self)
        self.broker = broker
        self.reader = reader
        self.writer = writer
        self.seq = 0

        ip, port = writer.get_extra_info('peername')
        self.addr = f"{ip}:{port}"

        print(f"[{self.addr}] Nova conexão estabelecida ({self.broker.id:08X}:{self.id:08X})")

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()
        self.broker.remove_connection(self)

    def expected_checksum(self, packet_len: int) -> int:
        next = ( (self.seq + packet_len) & 0xFFFF )
        return (17405 * next - 24893) & 0xFFFF

    def advance_seq(self, packet_len: int) -> None:
        self.seq = (self.seq + packet_len) & 0xFFFFFFFF

    async def handler(self):
        while True:
            try:
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
                await self.on_recv(packet_size, reader)
            finally:
                print(f"[{self.addr}] Fechando conexão")
                await self.close()
                break

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
            self.advance_seq(packet_size)
            await BasePackageFactory.from_data(cmd, self, buf)
        except UnknownPacketError as e:
            cmd = e.getcmd()
            print(f"[{self.addr}] UnknownPacketError command: {cmd:#04x}. Dump: \n")
            dump(e.buf.getvalue())
            raise e

    async def on_send(self, data: BasePackageSend):
        data.log_command(self)

        buf = data.get_buf()
        total_len = buf.size() + 4
        buf.write_uint16(total_len, pos=0, insert=True)
        buf.write_uint16(self.expected_checksum(total_len), pos=2, insert=True)
        
        try:
            self.writer.write(buf.getvalue())
            await self.writer.drain()
            self.advance_seq(total_len)
        except ConnectionResetError as e:
            print(f"[{self.addr}] Conexão perdida ao enviar dados: {e}")
            print(f"[{self.addr}] Cliente provavelmente desconectou abruptamente")
            await self.close()
        except BrokenPipeError as e:
            print(f"[{self.addr}] Pipe quebrado ao enviar dados: {e}")
            print(f"[{self.addr}] Possível problema de rede ou cliente desconectado")
            await self.close()
        except Exception as e:
            print(f"[{self.addr}] Erro desconhecido ao enviar dados: {type(e).__name__}: {e}")
            await self.close()
