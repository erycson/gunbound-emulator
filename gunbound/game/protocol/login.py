from __future__ import annotations
import socket
import asyncio
import time
from typing import TYPE_CHECKING, Dict, Any, List
from dependency_injector.wiring import Provide, inject
from gunbound.base.managers import CryptoManager
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util import BinaryWriter, BinaryReader
from gunbound.game.protocol.enums import ClientPacket, ServerPacket
if TYPE_CHECKING:
    from gunbound.repository import UserRepository, RecordsRepository, ServerRepository
    from gunbound.game.client import ClientConnection

@inject
@BasePackageFactory.register(ClientPacket.CLI_LOGIN.value)
class LoginRecv(BasePackageRecv):
    _strategy = None

    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        crypto: CryptoManager = Provide['Container.crypto'],
        user_repository: 'UserRepository' = Provide['Container.user_repository'],
        server_repository: 'ServerRepository' = Provide['Container.server_repository'],
        records_repository: 'RecordsRepository' = Provide['Container.records_repository'],
    ):
        self.conn = conn
        self.buf = buf
        self.crypto = crypto
        self.user_repository = user_repository
        self.server_repository = server_repository
        self.records_repository = records_repository

    async def process(self):
        username = self.crypto.decrypt(self.buf.read_bytes(16)).decode('latin-1').rstrip('\x00')
        signature = self.crypto.decrypt(self.buf.read_bytes(16))

        session_bytes = signature[0:4]
        session_id = int.from_bytes(session_bytes, 'little')
        
        async with self.conn.manager.lock:
            if (session_id != self.conn.manager.rand.current_value):
                print(f"[LoginRecv] Signature inválida. Recebida {session_id:08X}, esperada {self.conn.manager.rand.current_value:08X}")
                return

        client_ip, client_port = self.conn.writer.get_extra_info('peername')
        client_ip = int.from_bytes(socket.inet_aton(client_ip), 'little')

        profile, is_ip_blocked = await self.find_profile(username, client_ip)
        if not profile:
            print(f"[LoginStrategy] Usuário não encontrado: {username}")
            return
        elif is_ip_blocked:
            print(f"[LoginStrategy] Login bloqueado para IP do cliente: {is_ip_blocked} ->  {client_ip}")
            return

        user_key = self.crypto.derive_key(username, profile['Password'], session_bytes)

        # Valida a senha
        # PREFIXO(4) + Senha(12)
        block_1 = self.crypto.decrypt(self.buf.read_bytes(16), user_key)
        password = block_1[4:12].decode('latin-1').rstrip('\x00')
        if profile["Password"] != password:
            print(f"[LoginStrategy] Senha incorreta para usuário {username}")
            return

        # Valida a versão do cliente
        # PREFIXO(4) + Desconhecido(4) + Version(4)
        block_2 = self.crypto.decrypt(self.buf.read_bytes(16), user_key)
        is_invalid, client_version = self.is_invalid_version(block_2)
        if (is_invalid == False):
            await self.conn.on_send(LoginResp.wrong_version())
            print(f"[LoginStrategy] Recv Version({client_version})")
            return

        # Lê os dados de conexão IP, Port e valida o ProductVersion do cliente
        # PREFIXO(4) + IP(4) + Port(2) + ProductVersion(4) + Desconhecido(2)
        block_3 = self.crypto.decrypt(self.buf.read_bytes(16), user_key)
        conn_reader = BinaryReader(block_3)
        conn_ip = conn_reader.read_uint32(4)
        conn_port = conn_reader.read_uint16(6)
        product_version = conn_reader.read_uint32(10)
        if (product_version != self.conn.server.config['product_version']):
            await self.conn.on_send(LoginResp.wrong_version())
            print(f"[LoginStrategy] Recv ProductVersion({product_version})")
            return

        # Insere o usuário na tabela CurrentUser, e verifica se ele já está logado em outro GameServer
        is_inserted = await self.server_repository.insert_current_user(username, self.conn.id, self.conn.server.config['host'], self.conn.server.config['port'])
        if not is_inserted:
            print(f"[LoginStrategy] Usuário já está logado: {username}")
            return
        
        # Agora que tudo foi validado, obtém todos os dados do usuário
        game, stage, mobile = await self.get_login(username, client_ip, client_port, conn_ip, conn_port)
        self.conn.data = {
            'game': game,
            'profile': profile,
        }

        self.conn.set_token(self.conn.manager.rand.current_value)

        await self.conn.on_send(LoginResp.success(self.crypto, self.conn))
        await self.conn.on_send(LoginResp.success_record(stage, mobile))
        self.conn.is_alive()
        self.conn.last_activity = time.time()

    async def find_profile(self, username: str, client_ip: int) -> Dict[str, Dict[str, Any]]:
        """
        Descobrir como usar: User_Level, Authority, Authority2, RestrictTime
        """
        return await asyncio.gather(
            self.user_repository.get_profile(username),
            self.server_repository.is_ip_blocked(client_ip),
        )

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
            self.server_repository.insert_login_log(username, self.conn.server.config['host'], self.conn.server.config['port'], client_ip, client_port, conn_ip, conn_port),
        )

        return game, stage, mobile

    def is_invalid_version(self, block: bytes):
        version_reader = BinaryReader(block)
        client_version = version_reader.read_uint32(pos=8)
        version_min = self.conn.server.config['version_min']
        version_max = self.conn.server.config['version_max']
        is_invalid = client_version < version_min or client_version > version_max
        return is_invalid, client_version

    def log_command(self, conn):
        cmd = ClientPacket.CLI_LOGIN.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}] {self.buf.to_hex(4)}")

class LoginResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf

    @classmethod
    def success(cls, crypto: 'CryptoManager', conn: 'ClientConnection'):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(0)
        buf.write_uint32(conn.data['token'])
        buf.write_string(conn.data['profile']['Nickname'], 12)
        buf.write_uint8(conn.data['profile']['Gender'])
        buf.write_string(conn.data['game']['Guild'], 8)
        buf.write_int16(conn.data['game']['TotalGrade'])
        buf.write_int16(conn.data['game']['SeasonGrade'])
        buf.write_int16(conn.data['game']['CountryGrade'])
        buf.write_uint16(conn.data['game']['Country'])
        buf.write_uint16(conn.data['game']['MemberCount'])
        buf.write_uint32(conn.data['game']['TotalRank'])
        buf.write_uint32(conn.data['game']['SeasonRank'])
        buf.write_uint32(conn.data['game']['GuildRank'])
        buf.write_uint32(conn.data['game']['CountryRank'])
        buf.write_uint32(conn.data['game']['AccumShot'])
        buf.write_uint32(conn.data['game']['AccumDamage'])
        buf.write_uint32(conn.data['game']['TotalScore'])
        buf.write_uint32(conn.data['game']['SeasonScore'])
        buf.write_uint32(conn.data['game']['Money'])
        buf.write_uint32(conn.data['game']['EventScore0'])
        buf.write_uint32(conn.data['game']['EventScore1'])
        buf.write_uint32(conn.data['game']['EventScore2'])
        buf.write_uint32(conn.data['game']['EventScore3'])

        # Prefixo para os próximos blocos de 16 bytes de dados que serão criptografados
        prefix = ServerPacket.SRV_LOGIN.value - 0x79CE9F82
        server_buf = BinaryWriter()
        # Primeiros 12 bytes
        server_buf.write_int32(prefix)
        server_buf.write_uint32(conn.server.features)
        server_buf.write_uint32(conn.server.config['score_factor'])
        server_buf.write_uint32(conn.server.config['gold_factor'])
        # Próximos 12 bytes
        server_buf.write_int32(prefix)
        server_buf.write_uint32(conn.prng.generate_value()) # Provavelmente vai servir para sicronizar o PRNG do cliente
        server_buf.write_uint32(0) # Uso desconhecido
        server_buf.write_uint32(0) # Uso desconhecido

        # Criptografa os dados
        server_salt = conn.manager.rand.current_value.to_bytes(4, byteorder='little')
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
    def success_token(cls, conn: 'ClientConnection'):
        """
        Uso ainda não está certo, mas parece ser um token de autenticação adicional
        """
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN_TOKEN)
        buf.write_uint32(conn.prng.generate_value())
        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")