import socket
import asyncio
import time
from typing import Dict, Any, List
from gunbound.game.client import ClientConnection
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.base.managers import CryptoManager, ConfigManager
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.respository import UserRepository, RecordsRepository, ServerRepository

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
        self.server_repository: ServerRepository = ServerRepository()

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
        client_ip = int.from_bytes(socket.inet_aton(client_ip), 'little')

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
        conn_ip = conn_reader.read_uint32(4)
        conn_port = conn_reader.read_uint16(6)
        product_version = conn_reader.read_uint32(10)
        if (product_version != self.conn.server['product_version']):
            await self.conn.on_send(LoginResp.wrong_version())
            print(f"Recv ProductVersion({product_version})")
            return

        # Insere o usuário na tabela CurrentUser, e verifica se ele já está logado em outro GameServer
        is_inserted = await self.server_repository.insert_current_user(username, self.conn.id, self.conn.server.host, self.conn.server.port)
        if not is_inserted:
            return
        
        # Agora que tudo foi validado, obtém todos os dados do usuário
        game, stage, mobile = await self.get_login(username, client_ip, client_port, conn_ip, conn_port)
        data = {
            'game': game,
            'profile': login['profile'],
        }
        self.conn.data = data

        print(f"[LoginRecv] Usuário logado com sucesso", data)
        await self.conn.on_send(LoginResp.success(self.conn))
        await self.conn.on_send(LoginResp.success_record(stage, mobile))
        self.conn.is_alive()

    async def find_login(self, username: str, client_ip: int) -> Dict[str, Dict[str, Any]]:
        game, is_ip_blocked = await asyncio.gather(
            self.user_repository.get_profile(username),
            self.server_repository.is_ip_blocked(client_ip),
        )
        return {
            'profile': game,
            'is_ip_blocked': is_ip_blocked
        }

    async def get_login(self, username: str, client_ip: int, client_port: int, conn_ip: int, conn_port: int) -> Dict[str, Dict[str, Any]]:
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
        game, stage, mobile, _ = await asyncio.gather(
            self.user_repository.get_game(username),
            self.records_repository.get_stage(username),
            self.records_repository.get_mobile(username),
            self.server_repository.insert_login_log(username, self.conn.server.host, self.conn.server.port, client_ip, client_port, conn_ip, conn_port),
        )

        return {
            'game': game,
            'stage': stage,
            'mobile': mobile,
        }

    def is_invalid_version(self, block: bytes):
        version_reader = BinaryReader(block)
        client_version = version_reader.read_uint32(pos=8)
        version_min = self.conn.server['version_min']
        version_max = self.conn.server['version_max']
        is_invalid = client_version < version_min or client_version > version_max
        return is_invalid, client_version

    def log_command(self, conn):
        cmd = ClientPacket.CLI_LOGIN.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex()}")

class LoginResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf

    @classmethod
    def success(cls, conn: ClientConnection):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint16(0)
        buf.write_uint32(conn.id)
        buf.write_string(conn.data['profile']['NickName'], 12)
        buf.write_uint8(conn.data['profile']['Gender'])
        buf.write_string(conn.data['game']['Guild'], 8)
        buf.write_uint16(conn.data['game']['TotalGrade'])
        buf.write_uint16(conn.data['game']['SeasonGrade'])
        buf.write_uint16(conn.data['game']['CountryGrade'])
        buf.write_uint16(conn.data['game']['MemberCount'])
        buf.write_uint16(conn.data['game']['TotalRank'])
        buf.write_uint16(conn.data['game']['SeasonRank'])
        buf.write_uint16(conn.data['game']['GuildRank'])
        buf.write_uint16(conn.data['game']['CountryRank'])
        buf.write_uint16(conn.data['game']['AccumShot'])
        buf.write_uint16(conn.data['game']['AccumDamage'])
        buf.write_uint16(conn.data['game']['TotalScore'])
        buf.write_uint16(conn.data['game']['SeasonScore'])
        buf.write_uint16(conn.data['game']['Money'])
        buf.write_uint16(conn.data['game']['EventScore0'])
        buf.write_uint16(conn.data['game']['EventScore1'])
        buf.write_uint16(conn.data['game']['EventScore2'])
        buf.write_uint16(conn.data['game']['EventScore3'])

        # Prefixo para os próximos blocos de 16 bytes de dados que serão criptografados
        prefix = ServerPacket.SRV_LOGIN.value - 0x79CE9F82
        server_buf = BinaryWriter()
        # Primeiros 12 bytes
        server_buf.write_uint32(prefix)
        server_buf.write_uint32(conn.server.features)
        server_buf.write_uint32(conn.server['score_factor'])
        server_buf.write_uint32(conn.server['gold_factor'])
        # Próximos 12 bytes
        server_buf.write_uint32(prefix)
        server_buf.write_uint32(conn.prng.generate_value()) # Provavelmente vai servir para sicronizar o PRNG do cliente
        server_buf.write_uint32(0) # Uso desconhecido
        server_buf.write_uint32(0) # Uso desconhecido

        # pega os dados 
        crypto = CryptoManager.get()
        server_salt = conn.manager.rand().to_bytes(4, byteorder='little')
        server_derived_key = crypto.derive_key(conn.data['profile']['User'], conn.data['profile']['Password'], server_salt)
        server_crypted = crypto.encrypt(server_buf.getvalue(), server_derived_key)
        buf.write_bytes(server_crypted)

        return cls(buf)
    
    @classmethod
    def success_record(cls, stage: List[Dict[str, Any]], mobile: List[Dict[str, Any]]):
        """Uso desconhecido"""
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN_RECORD)

        buf.write_uint16(len(stage))
        for record in stage:
            buf.write_uint32(record['Stage'])
            buf.write_uint32(record['Win'])
            buf.write_uint32(record['Lose'])

        buf.write_uint16(len(mobile))
        for record in mobile:
            buf.write_uint32(record['Mobile'])
            buf.write_uint32(record['Win'])
            buf.write_uint32(record['Lose'])

        return cls(buf)
    
    @classmethod
    def success_token(cls, conn: ClientConnection):
        """
        Uso ainda não está certo, mas parece ser um token de autenticação adicional
        """
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN_TOKEN)
        buf.write_bytes(conn.prng.generate_value())
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