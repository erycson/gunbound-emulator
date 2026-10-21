from __future__ import annotations
import hashlib
import socket
from datetime import datetime
import asyncio
import time
from typing import TYPE_CHECKING, Dict, Any, List
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util import BinaryWriter, BinaryReader
from gunbound.game import phase
from gunbound.game.protocol.base import Packet
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.repository import UserRepository, RecordsRepository, ServerRepository
    from gunbound.game.client import ClientConnection

def check_password(crypto, username: str, password: str, session_bytes: bytes, raw_1: bytes, raw_2: bytes):
    """Senha nos 20 bytes block_1[4:16] + block_2[4:12]; tenta a pura e o md5[12:32].
    Devolve (chave, block_2, senha que bateu) ou None: o cliente deriva a chave da sessão da mesma senha."""
    md5_pw = hashlib.md5(password.encode('latin-1')).hexdigest()[12:32]
    for expected in (password, md5_pw):
        user_key = crypto.derive_key(username, expected, session_bytes)
        block_1, block_2 = crypto.decrypt(raw_1, user_key), crypto.decrypt(raw_2, user_key)
        if (block_1[4:16] + block_2[4:12]).decode('latin-1').rstrip('\x00') == expected:
            return user_key, block_2, expected
    return None


LIMIT_FREE_AUTHORITY = 98  # Authority >= 98 passa direto pelos limites de patente/guild


def login_limit(game: dict, authority: int, config) -> int | None:
    """RTC de recusa do 0x1012 (S3) ou None. Original 2006 0x42d790 / 2007 0x433cc2, na mesma ordem."""
    if authority >= LIMIT_FREE_AUTHORITY:
        return None
    lo, hi = sorted((int(config.get('grade_min', -4)), int(config.get('grade_max', 19))))  # o config.yml guarda 19/-4
    if not lo <= int(game.get('TotalGrade') or 0) <= hi:
        return ServerCode.SRV_GRADE_LIMIT
    guild = (game.get('Guild') or '')[:8]
    mark = int(config.get('guild_limit') or 0)  # GuildMarkLimit
    if mark == 1 and not guild:
        return ServerCode.SRV_GUILD_REQUIRED
    if mark == 2 and guild:
        return ServerCode.SRV_GUILD_FORBIDDEN
    allowed = config.get('allowed_guild') or []  # AllowedGuild.txt: lista vazia = todas (0x407250)
    if allowed and guild not in allowed:
        return ServerCode.SRV_GUILD_NOT_ALLOWED
    return None


@BasePackageFactory.register(ClientPacket.CLI_ADMIN_LOGIN.value)  # SVC_LOGIN/ADMIN usa o mesmo handler no original
@BasePackageFactory.register(ClientPacket.CLI_LOGIN.value)
@inject
class LoginRecv(BasePackageRecv):
    _strategy = None

    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        user_repository: 'UserRepository' = Provide['user_repository'],
        server_repository: 'ServerRepository' = Provide['server_repository'],
        records_repository: 'RecordsRepository' = Provide['records_repository'],
    ):
        self.conn = conn
        self.buf = buf
        self.crypto_manager = conn.crypto_manager
        self.user_repository = user_repository
        self.server_repository = server_repository
        self.records_repository = records_repository

    async def process(self):
        username = self.crypto_manager.decrypt(self.buf.read_bytes(16)).decode('latin-1').rstrip('\x00')
        signature = self.crypto_manager.decrypt(self.buf.read_bytes(16))

        session_bytes = signature[0:4]
        session_id = int.from_bytes(session_bytes, 'little')
        
        async with self.conn.client_manager.lock:
            if (session_id != self.conn.client_manager.rand.current_value):
                print(f"[LoginRecv] Signature inválida. Recebida {session_id:08X}, esperada {self.conn.client_manager.rand.current_value:08X}")
                return

        client_ip, client_port = self.conn.writer.get_extra_info('peername')
        client_ip = int.from_bytes(socket.inet_aton(client_ip), 'little')

        profile, is_ip_blocked = await self.find_profile(username, client_ip)
        if not profile:
            print(f"[Login] Usuário não encontrado: {username}")
            return
        elif is_ip_blocked:
            print(f"[Login] Login bloqueado para IP do cliente: {is_ip_blocked} ->  {client_ip}")
            return
        elif profile.get('RestrictTime') and profile['RestrictTime'] > datetime.now():
            print(f"[Login] Usuário banido até {profile['RestrictTime']}: {username}")
            return

        # Senha em campo fixo de 20 bytes (block_1[4:16] + block_2[4:12]): pura no cliente direto, md5(senha) em hex [12:32]
        # via NyxLauncher. Versão sempre em block_2[12:16]: TH 404, S1 440/495, S2 531/548, v584 manda 4 (RE dos clientes + logs)
        raw_1, raw_2 = self.buf.read_bytes(16), self.buf.read_bytes(16)
        checked = check_password(self.crypto_manager, username, profile['Password'], session_bytes, raw_1, raw_2)
        if checked is None:
            print(f"[Login] Senha incorreta para usuário {username}")
            return
        user_key, block_2, key_password = checked

        # Valida a versão do cliente
        is_invalid, client_version = self.is_invalid_version(block_2, 12)
        if is_invalid:
            print(f"[Login] Recv Version({client_version})")
            await self.conn.on_send(LoginResp.wrong_version())
            return

        # Lê os dados de conexão IP, Port e valida o ProductVersion do cliente
        # PREFIXO(4) + IP(4) + Port(2) + ProductVersion(4) + Desconhecido(2)
        block_3 = self.crypto_manager.decrypt(self.buf.read_bytes(16), user_key)
        conn_reader = BinaryReader(block_3)
        conn_ip = conn_reader.read_uint32(4)
        conn_port = int.from_bytes(block_3[8:10], 'big')  # IP em 4..7, porta em 8..9 (ordem de rede); antes lia em 6 = fim do IP
        print(f"[LoginRecv] UDP informado pelo cliente: {socket.inet_ntoa(block_3[4:8])}:{conn_port}")
        product_version = conn_reader.read_uint32(10)
        if product_version != self.conn.server.config['product_version'] and product_version not in phase.of(self.conn).product_versions:
            print(f"[Login] Recv ProductVersion({product_version} = 0x{product_version:08X})")
            await self.conn.on_send(LoginResp.wrong_version())
            return

        # Limites de patente/guild antes do claim_session: um re-login recusado não derruba a sessão que já está aberta
        game = await self.user_repository.get_game(username)
        refused = login_limit(game, int(profile.get('Authority') or 0), self.conn.server.config)
        if refused is not None:
            print(f"[Login] {username} recusado pelos limites de patente/guild (RTC 0x{refused:04X})")
            await self.conn.on_send(LoginResp.refused(refused))
            return

        # Mesmo usuário já logado NESTE GameServer: derruba a sessão antiga (o close dela limpa o CurrentUser)
        await self.conn.client_manager.claim_session(username, self.conn)

        # Insere o usuário na tabela CurrentUser, e verifica se ele já está logado em outro GameServer
        is_inserted = await self.server_repository.insert_current_user(username, self.conn.id, self.conn.server.config['host'], self.conn.server.config['port'])
        if not is_inserted:
            print(f"[Login] Usuário já está logado em outro servidor: {username}")
            self.conn.client_manager.release_session(username, self.conn)
            await self.conn.close()
            return
        
        # Agora que tudo foi validado, obtém todos os dados do usuário
        stage, mobile = await self.get_login(username, client_ip, client_port, conn_ip, conn_port)
        self.conn.data = {
            'game': game,
            'profile': profile,
            'net': (conn_ip, conn_port),  # IP/porta UDP informados pelo cliente, repassados aos outros da sala
            'client_version': client_version,  # v548 manda 548, v584 manda 4 (logs de 2026-10-19); muda o 0x6001 (phase.chest_tail)
            # via NyxLauncher o cliente usa o md5[12:32] também na chave da sessão (x64dbg no v584, 2026-10-21):
            # com a senha pura os pacotes cifrados S->C (0x3432, 0x4410...) chegavam zerados
            'key_password': key_password,
        }

        self.conn.set_token(self.conn.client_manager.rand.current_value)

        await self.conn.on_send(LoginResp.success(self.conn))
        if phase.is_v584(self.conn):
            # tipo do canal (v584 0x514faf, antes do 0x2001): 2 = Stage. O cliente nunca zera: os outros servidores mandam 0
            await self.conn.on_send(Packet.new(0x1111).u8(2 if phase.is_stage(self.conn) else 0))
        from gunbound.game.anticheat import AntiCheat
        self.conn.anticheat = AntiCheat.from_config(self.conn)
        self.conn.anticheat.start()  # o original manda o 0x1015 logo depois do 0x1012 (servidor 2007)
        if not phase.is_v584(self.conn):
            # v584 (0x40f8d8) lê o 0x1013 como bloco de 0x40 bytes (+0 = TotalScore): os records do v440 viram lixo no GP
            await self.conn.on_send(LoginResp.success_record(stage, mobile))
        if (ready := phase.of(self.conn).login_ready) is not None:
            await self.conn.on_send(Packet.new(ready, rtc=0))
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
        stage, mobile, _ = await asyncio.gather(
            self.records_repository.get_stage(username),
            self.records_repository.get_mobile(username),
            self.server_repository.insert_login_log(username, self.conn.server.config['host'], self.conn.server.config['port'], client_ip, client_port, conn_ip, conn_port),
        )

        return stage, mobile

    def is_invalid_version(self, block: bytes, pos: int = 12):
        version_reader = BinaryReader(block)
        client_version = version_reader.read_uint32(pos=pos)
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
    def success(cls, conn: 'ClientConnection'):
        crypto_manager = conn.crypto_manager
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(0)
        buf.write_uint32(conn.data['token'])
        buf.write_string(conn.data['profile']['Nickname'], 12)
        buf.write_uint8(conn.data['profile']['Gender'])
        buf.write_string(conn.data['game']['Guild'], 8)
        layout = phase.of(conn)
        buf.write_bytes(layout.grades(conn.data['game']))
        buf.write_bytes(layout.login_stats(conn.data['game'], conn.data.get('client_version', 0)))

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
        server_salt = conn.client_manager.rand.current_value.to_bytes(4, byteorder='little')
        server_derived_key = crypto_manager.derive_key(conn.data['profile']['User'], conn.data.get('key_password', conn.data['profile']['Password']), server_salt)
        server_crypted = crypto_manager.encrypt(server_buf.getvalue(), server_derived_key)
        buf.write_bytes(server_crypted)

        return cls(buf)
    
    @classmethod
    def refused(cls, code: int):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(code)
        return cls(buf)

    @classmethod
    def wrong_version(cls):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_LOGIN)
        buf.write_uint16(ServerCode.SRV_WRONG_VERSION)
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
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")