import asyncio
import socket
from typing import Dict, Any
from gunbound.game.client import ClientConnection
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.base.managers import CryptoManager, ConfigManager
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util import dump
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.respository import UserRepository, InventoryRepository, RecordsRepository, SecurityRepository

"""
A inicialização da criptografia dos dados enviado pelo cliente é feita pela função sub_40B420 no GBS v440
"""
@BasePackageFactory.register(ClientPacket.CLI_LOGIN.value)
class LoginRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn: ClientConnection, buf: BinaryReader):
        self.conn = conn
        self.buf = buf
        self.crypto: CryptoManager = CryptoManager.get()
        self.sign_key: bytes = bytes.fromhex(ConfigManager.get()['crypto']['game_key'])
        self.user_repository: UserRepository = UserRepository()
        self.records_repository: RecordsRepository = RecordsRepository()
        self.inventory_repository: InventoryRepository = InventoryRepository()
        self.security_repository: SecurityRepository = SecurityRepository()

    async def process(self):
        print(f"[LoginRecv] Processing login packet...: ({self.buf.size()})  {self.buf.to_hex()}")        
        username = self.crypto.decrypt(self.buf.read_bytes(16)).decode('latin-1').rstrip('\x00')
        signature = self.crypto.decrypt(self.buf.read_bytes(16)) # bytes.fromhex('FFB3B3BEAE97AD83B9610E23A43C2EB0')

        session_bytes = signature[0:4]
        session_id = int.from_bytes(session_bytes, 'little')
        if (session_id != self.conn.id):
            print(f"[LoginRecv] Signature inválida. Recebida {session_id:08X}, esperada {self.conn.id:08X}")
            return

        client_ip, client_port = self.conn.writer.get_extra_info('peername')
        client_ip = int.from_bytes(socket.inet_aton(client_ip), 'big')

        login = await self.find_login(username, client_ip)
        print(login)
        if not login['profile']:
            print(f"[LoginStrategy] Usuário não encontrado: {username}")
            return
        elif login['is_ip_blocked']:
            print(f"[LoginStrategy] Login bloqueado para IP do cliente: {login['is_ip_blocked']} ->  {client_ip}")
            return

        user_key = self.crypto.derive_key(username, login['profile']['Password'], session_bytes)

        # Valida a senha
        # PREFIXO(4) + Senha(12)
        block_1 = self.crypto.decrypt(self.buf.read_bytes(16), user_key)
        password = block_1[4:12].decode('latin-1').rstrip('\x00')
        if login['profile']["Password"] != password:
            print(f"[LoginStrategy] Senha incorreta para usuário {username}")
            return

        # Valida a versão do cliente
        # PREFIXO(4) + Desconhecido(4) + Version(4)
        block_2 = self.crypto.decrypt(self.buf.read_bytes(16), user_key)
        is_invalid, client_version = self.is_invalid_version(block_2)
        if (is_invalid == False):
            await self.conn.on_send(LoginResp.wrong_version())
            print(f"Recv Version({client_version})")
            return

        # Lê os dados de conexão IP, Port e valida o ProductVersion do cliente
        # PREFIXO(4) + IP(4) + Port(2) + ProductVersion(4) + Desconhecido(2)
        block_3 = self.crypto.decrypt(self.buf.read_bytes(16), user_key)
        conn_reader = BinaryReader(block_3)
        conn_ip = conn_reader.read_uint32()
        conn_port = conn_reader.read_uint16()
        product_version = conn_reader.read_uint32()
        if (product_version != self.conn.server.product_version):
            await self.conn.on_send(LoginResp.wrong_version())
            print(f"Recv ProductVersion({product_version})")
            return

        # Agora que tudo foi validado
        data = await self.get_login(username, client_ip)
        data['profile'] = login['profile']

        await self.insert_login(username, self.conn.server.id, self.conn.server.host, self.conn.server.port, client_ip, client_port, conn_ip, conn_port)

        print(f"[LoginRecv] Usuário logado com sucesso", data)

    async def find_login(self, username: str, client_ip: int) -> Dict[str, Dict[str, Any]]:
        game, is_ip_blocked = await asyncio.gather(
            self.user_repository.get_profile(username),
            self.security_repository.is_ip_blocked(client_ip),
            self.security_repository.is_ip_blocked(client_ip),
        )
        return {
            'profile': game,
            'is_ip_blocked': is_ip_blocked
        }

    async def get_login(self, username: str, client_ip: int) -> Dict[str, Dict[str, Any]]:
        """
        Retorna todos os dados do usuário necessários para o login.
        Args:
            username (str): O identificador único do usuário.
            context (int): Identificador de contexto da sessão.
            server_ip (int): Endereço IP do servidor.
            server_port (int): Número da porta do servidor.
            client_ip (int): Endereço IP do cliente.
            client_port (int): Número da porta do cliente.

        Returns:
            Optional[Dict[str, Any]]: Dicionário com dados do usuário se bem-sucedido,
            None se usuário não encontrado ou bloqueado.
        """
        game, stage_records, mobile_records, is_ip_blocked, chest, cash, money, gift_msgs = await asyncio.gather(
            self.user_repository.get_stats(username),
            self.records_repository.get_stage_records(username),
            self.records_repository.get_mobile_records(username),
            self.security_repository.is_ip_blocked(client_ip),
            self.inventory_repository.get_chest(username),
            self.inventory_repository.get_cash(username),
            self.inventory_repository.get_money(username),
            self.user_repository.get_gift_msgs(username)
        )

        return {
            'game': game,
            'stage_records': stage_records,
            'mobile_records': mobile_records,
            'is_ip_blocked': is_ip_blocked,
            'chest': chest,
            'cash': cash,
            'money': money,
            'gifts': gift_msgs
        }
    
    async def insert_login(self, username: str, context: int, server_ip: int, server_port: int, client_ip: int, client_port: int): 
        await asyncio.gather(
            self.security_repository.insert_current_user(username, context, server_ip, server_port),
            self.security_repository.insert_login_log(username, client_ip, client_port, server_ip, server_port)
        )

    def is_invalid_version(self, block: bytes):
        version_reader = BinaryReader(block)
        client_version = version_reader.read_uint32(pos=8)
        version_min = self.conn.server.version_min
        version_max = self.conn.server.version_max
        is_invalid = client_version < version_min or client_version > version_max
        return is_invalid, client_version

    def log_command(self, conn):
        cmd = ClientPacket.CLI_LOGIN.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex()}")

class LoginResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    """
    04 D1 00 00 -> SessionId 1233
    """
    # @classmethod
    # def success(cls, session_id: int):
    #     buf = BinaryWriter()
    #     buf.write_uint16(ServerPacket.SRV_LOGIN)
    #     buf.write_uint32(session_id)
    #     return cls(buf)
    
    """
    10 12 00 60
    """
    @classmethod
    def wrong_version(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(ServerCode.SRV_WRONG_VERSION)
        return cls(buf)
    
    def get_buf(self) -> BinaryWriter:
        return self.buf
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        if (rtc == 0):
            print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex()}")
        else:
            print(f"SEND>> [SS={conn.broker.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}]")