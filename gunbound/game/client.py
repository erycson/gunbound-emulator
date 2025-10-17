from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict
from asyncio import CancelledError, Task, StreamReader, StreamWriter
from gunbound.base.protocol import BasePackageFactory, BasePackageSend
from gunbound.base.managers import CryptoManager
from gunbound.game.channel import Channel
from gunbound.game.room import Room
from gunbound.util import BinaryReader, GBWCGenerator
if TYPE_CHECKING:
    from gunbound import GameServer
    from gunbound.repository import ServerRepository, UserRepository
    from gunbound.game.managers import ClientManager, CryptoManager

class ClientConnection:
    def __init__(
        self,
        prng_seed: int,
        reader: StreamReader,
        writer: StreamWriter,
    ):
        """
        Representa uma conexão de cliente.
        Args:
            server: Instância do servidor ao qual o cliente está conectado.
            manager: Gerenciador de conexões de clientes.
            id (int): Identificador único da conexão do cliente.
            reader (StreamReader): StreamReader para ler dados do cliente.
            writer (StreamWriter): StreamWriter para enviar dados ao cliente.
        """
        self.id = id(self) & 0xFFFFFFFF
        self.server: 'GameServer' = None
        self.client_manager: 'ClientManager' = None
        self.crypto_manager: 'CryptoManager' = None
        self.user_repository: 'UserRepository' = None
        self.server_repository: 'ServerRepository' = None
        self.reader: StreamReader = reader
        self.writer: StreamWriter = writer
        self.client_seq: int = 0 # Não sei se é compartilhado com outras conexões
        self.server_seq: int = 0
        self.task: Task | None = None
        self.closing: bool = False
        self.prng: GBWCGenerator = GBWCGenerator(prng_seed)
        self.data: Dict[str, Any] = {}
        self.last_activity: float = time.time() - 301 # o 301 é pra forçar o envio do token
        self.is_authenticated: bool = False
        self.channel: Channel | None = None
        self.room: Room | None = None

        ip, port = writer.get_extra_info('peername')
        self.addr: str = f"{ip}:{port}"

        print(f"[{self.addr}] ClientConnection({self.server.id:08X}:{self.id:08X})")

    def set_token(self, token: int) -> None:
        self.data['token'] = token
        self.data['derived_key'] = self.crypto_manager.derive_key(
            self.data['profile']['Id'],
            self.data['profile']['Password'],
            token.to_bytes(4, 'little', signed=False)
        )

    def get_derived_key(self) -> bytes | None:
        return self.data['derived_key'] if 'derived_key' in self.data else None
    
    def decrypt(self, data: bytes) -> bytes:
        return self.crypto_manager.decrypt(data, self.get_derived_key())
    
    def encrypt(self, data: bytes) -> bytes:
        return self.crypto_manager.encrypt(data, self.get_derived_key())

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
    
    def is_alive(self) -> bool:
        """
        Verifica se a conexão está ativa com base na última atividade.
        """
        from gunbound.game.protocol.login import LoginResp

        now = time.time()
        if now - self.last_activity <= 600:
            if now - self.last_activity > 300 and not self.is_authenticated:
                asyncio.create_task(self.on_send(LoginResp.success_token(self)))
                self.is_authenticated = True
            return True
        
        return False

    async def disconnect(self):
        self.writer.close()
        await self.writer.wait_closed()

    async def close(self):
        if self.closing:
            return
        self.closing = True

        if self.channel is not None:
            await self.channel.remove(self)

        if 'profile' in self.data:
            await asyncio.gather(
                self.server_repository.delete_current_user(self.data['profile']['Id']),
                self.user_repository.update_clientdata(self.data['profile']['Id'], self.data['game']['ClientData'])
            )

        try:
            await self.disconnect()
            self.task.cancel()
            await self.task
        except CancelledError:
            pass
        finally:
            await self.client_manager.remove(self)

        print(f"[{self.addr}] ClientConnection({self.server.id:08X}:{self.id:08X}) closed")
    
    async def handler(self):
        while True:
            # Leia o cabeçalho inicial (2 bytes para o tamanho, little-endian)
            header = await self.reader.read(2)
            if len(header) < 2:
                await self.close()
                break

            # Ignore pacotes com tamanho inválido (ex: menor que header)
            packet_size = int.from_bytes(header, 'little', signed=False)
            if packet_size < 6:
                print(f"[{self.id:08X}] Tamanho do pacote inválido, ignorando")
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
        if checksum != expected:
            print(f"[{self.addr}] CHECKSUM FAIL< got={checksum:04X} exp={expected:04X} len={packet_size} cmd=0x{cmd:04X}")
            return

        # Processa o pacote
        self.advance_client_seq(packet_size)
        await BasePackageFactory.from_data(cmd, self, buf)

    async def on_send(self, packet: BasePackageSend):
        """
        Envia um pacote para o cliente.

        Args:
            packet (BasePackageSend): O pacote a ser enviado.
        """
        total_len = packet.buf.size() + 4
        packet.buf.write_uint16(total_len, pos=0, insert=True)
        packet.buf.write_uint16(self.expected_server_checksum(total_len), pos=2, insert=True)

        # Log do comando
        packet.log_command(self)

        # Criptografa se necessário, usando a chave derivada da autenticação
        packet.encrypt(self)
        
        try:
            self.writer.write(packet.buf.getvalue())
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
