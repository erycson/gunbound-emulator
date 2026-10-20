from asyncio import CancelledError, IncompleteReadError, StreamWriter, StreamReader, Task
from gunbound.base.protocol import BasePackageFactory, BasePackageSend
from gunbound.util import BinaryReader

class ClientConnection:
    def __init__(self, broker, reader: StreamReader, writer: StreamWriter):
        self.id = id(self) & 0xFFFFFFFF
        self.broker = broker
        self.reader: StreamReader = reader
        self.writer: StreamWriter = writer
        self.client_seq = 0 # Não sei se é compartilhado com outras conexões
        self.server_seq = 0
        self.closing: bool = False
        self.task: Task | None = None
        self.th = False  # conectou pela broker.th_port (layout TH no 0x1102)
        self.logged_in = False  # 0x1310 aceito (o 0x4000 do launcher exige)

        ip, port = writer.get_extra_info('peername')
        self.addr = f"{ip}:{port}"

        print(f"[{self.addr}] ClientConnection({self.broker.id:08X}:{self.id:08X})")

    async def disconnect(self):
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass  # socket já caiu (RST/WinError 64): fechar mesmo assim

    async def close(self):
        if self.closing:
            return
        self.closing = True

        try:
            await self.disconnect()
            self.task.cancel()
            await self.task
        except CancelledError:
            pass
        finally:
            self.broker.remove(self)

    def is_closed(self):
        return self.writer.is_closing()

    def expected_client_checksum(self, packet_len: int) -> int:
        next = (self.client_seq + packet_len) & 0xFFFF
        return (17405 * next - 24893) & 0xFFFF

    def advance_client_seq(self, packet_len: int) -> None:
        self.client_seq = (self.client_seq + packet_len) & 0xFFFF
    
    def expected_server_checksum(self, packet_len: int) -> int:
        next = (self.server_seq + packet_len) & 0xFFFF
        return (17405 * next - 21501) & 0xFFFF

    def advance_server_seq(self, packet_len: int) -> None:
        self.server_seq = (self.server_seq + packet_len) & 0xFFFF

    async def handler(self):
        try:
            await self.read_loop()
        except (ConnectionError, IncompleteReadError) as e:
            # Cliente morto (ex.: processo fechado) chega como RST/WinError 64; sem isso a task morria com
            # a exceção e o stop() do broker a relançava no desligamento
            print(f"[{self.addr}] Conexão perdida: {e!r}")
            await self.close()

    async def read_loop(self):
        while True:
            # Leia o cabeçalho inicial (2 bytes para o tamanho, little-endian)
            header = await self.reader.read(2)
            if len(header) < 2:
                await self.close()
                break

            # Ignore pacotes com tamanho inválido (ex: menor que header)
            packet_size = int.from_bytes(header, 'little', signed=False)
            if packet_size < 6:
                continue
            
            # Leia o restante do pacote
            payload = await self.reader.readexactly(packet_size - 2)
            reader = BinaryReader(payload)
            await self.on_recv(packet_size, reader)

    async def on_recv(self, packet_size: int, buf: BinaryReader):
        checksum = buf.read_uint16()
        cmd = buf.read_uint16()

        # Valida o pacote
        expected = self.expected_client_checksum(packet_size)
        # NyxLauncher manda login (0x1310) e start game (0x4000) com checksum 0
        if checksum != expected and not (checksum == 0 and cmd in (0x1310, 0x4000)):
            print(f"[{self.addr}] CHECKSUM FAIL< got={checksum:04X} exp={expected:04X} len={packet_size} cmd=0x{cmd:04X}")
            return

        # Processa o pacote
        self.advance_client_seq(packet_size)
        await BasePackageFactory.from_data(cmd, self, buf)

    async def on_send(self, data: BasePackageSend):
        if self.is_closed():
            print(f"[{self.addr}] Conexão fechada, não é possível enviar dados")
            return

        buf = data.get_buf()
        total_len = buf.size() + 4
        buf.write_uint16(total_len, pos=0, insert=True)
        buf.write_uint16(self.expected_server_checksum(total_len), pos=2, insert=True)

        data.log_command(self)
        
        try:
            self.writer.write(buf.getvalue())
            await self.writer.drain()
            self.advance_server_seq(total_len)
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
