"""
BuddyServ (amigos), protocolo lido no cliente TH v404 (CBuddy2, OnMsg 0x4e8c00, SendServ 0x4e9b90) e no BuddyServ2.exe.

Framing: u16 tamanho total (com o cabeçalho) + u16 comando + corpo. Sem sequência/checksum (diferente do game).
Cifra: AES-ECB em blocos de 16 = u32 BUDDY_MAGIC fixo + 12 bytes. Chave de sessão = derive_key(id, senha, nonce LE),
a mesma conta do login do game. Só 0x1010 (parte), 0x2000, 0x2030 (C->S) e 0x2010 (S->C) são cifrados.

Fluxo: cliente conecta e manda 0x1000 -> 0x1001 nonce -> 0x1010 login -> 0x1011 (lista) + 0x3FFF (estado dos amigos)
+ 0x2010 (mensagens guardadas). O cliente manda o token do 0x1011 por UDP para a mesma porta: é o endereço público
usado no P2P. Pedido de amizade, chat e remoção são P2P (c041/c042/c011/c043): sem rota UDP vão pelo túnel 0x2020,
que o servidor só repassa como 0x2021; para quem está offline o cliente usa 0x2000 e recebe no próximo login (0x2010).

WC S2 v584 (Buddy2.dll, versão 0x1B; docs/BuddyServ.md): Id de 20 bytes e nick/guild em UTF-16 (wchar[20]) em todos
os pacotes; 0x1001 de 8 bytes (nonce + máscara de recursos); login 0x1010 de 0xD0 bytes com senha VAZIA (o servidor
confere a sessão do game no lugar); a lista vai no 0x1012, antes de um 0x1011 só com rtc + token. O 0x1000 é igual
nas duas versões, então o servidor manda os dois 0x1001 e cada cliente lê só o seu tamanho.
"""
from __future__ import annotations
import asyncio
import hashlib
import os
import struct
import time
from typing import Dict, Optional
from gunbound.base.helpers import to_datetime
from gunbound.base.managers.crypto import CryptoManager
from gunbound.util.binary_buffer import BinaryReader, BinaryWriter, PacketError

STATIC_KEY = "2C45926CF3396642B670D006A1FA8182"  # DAT_005516b4 do cliente TH; outra que a game_key
BUDDY_MAGIC = 0x2DBABE65                          # 0x4e909e/0x4fa850: fixo, não soma o comando
LOGIN_VERSION = 0x19                              # 1º u32 do bloco cifrado do 0x1010 [INCERTO: versão do protocolo]
MAX_TUNNEL_DEST = 500

# C->S
SVC_KEEPALIVE, SVC_PRECREDENTIAL, SVC_LOGIN = 0x0000, 0x1000, 0x1010
SVC_SAVE_PACKET, SVC_SAVE_PACKET_ACK, SVC_TUNNEL, SVC_SMS = 0x2000, 0x2011, 0x2020, 0x2030
SVC_ADD_BUDDY, SVC_REMOVE_BUDDY, SVC_GROUP_BUDDY, SVC_RENAME_GROUP, SVC_USER_STATE = 0x3000, 0x3002, 0x3004, 0x3006, 0x3010
SVC_SEARCH = 0x4000
# S->C
RET_PRECREDENTIAL, RET_LOGIN, NTF_NOTICE = 0x1001, 0x1011, 0x1FFE
NTF_SAVE_PACKET, NTF_TUNNEL_PACKET, RET_SMS = 0x2010, 0x2021, 0x2031
RET_ADD_BUDDY, RET_REMOVE_BUDDY, RET_GROUP_BUDDY, RET_RENAME_GROUP = 0x3001, 0x3003, 0x3005, 0x3007
NTF_USER_STATE, RET_SEARCH = 0x3FFF, 0x4001

NTF_VIP_IPPORT, NTF_CLOSE_CONNECTION = 0x101F, 0x1FFF
OK, FAIL, BAD_SIZE, TOO_MANY = 0, 4, 7, 9
NOT_FOUND, BAD_PASSWORD, LIST_FULL, BAD_VERSION = 0x10, 0x11, 0x50, 0x60  # rtc do BuddyServ2 original
MAX_BUDDIES, MAX_SAVED_PER_PACKET = 500, 15
VERSION_FIRST, VERSION_LAST = 0, 600  # Setting.txt do original (VersionFirst/VersionLast)
P2P_SMS = 0xC013  # SVC_SEND_SMS: o 0x2030 chega ao destino como chat tipo 1
# v584 (Buddy2.dll)
RET_BUDDY_LIST = 0x1012
V584_VERSION, V584_LOGIN_SIZE = 0x1B, 0xD0
V584_FEATURES = 0x7601   # bits dos métodos que o .gme usa (login, c011/c021, c051, c041, c042+0x3000, 0x3002+c043)
V584_SMS = 0xC015
V584_LIST_MAX = 175      # entradas de 0x94 bytes por 0x1012 (buffer de 26000 do cliente)


def packet(cmd: int, body: bytes = b'') -> bytes:
    return struct.pack('<HH', len(body) + 4, cmd) + body


def cstr(raw: bytes) -> str:
    return raw.split(b'\0', 1)[0].decode('latin-1')


def fixed(text: str, size: int) -> bytes:
    return (text or '').encode('latin-1', errors='replace')[:size].ljust(size, b'\0')


def encrypt_blocks(crypto: CryptoManager, key: bytes, data: bytes) -> bytes:
    out = bytearray()
    for i in range(0, max(len(data), 1), 12):
        out += struct.pack('<I', BUDDY_MAGIC) + data[i:i + 12].ljust(12, b'\0')
    return crypto.encrypt(bytes(out), key)


def decrypt_blocks(crypto: CryptoManager, key: bytes, data: bytes) -> Optional[bytes]:
    """None se o tamanho não fecha em blocos ou se algum bloco não traz o magic (chave errada)."""
    if not data or len(data) % 16:
        return None
    plain = crypto.decrypt(data, key)
    if any(struct.unpack_from('<I', plain, i)[0] != BUDDY_MAGIC for i in range(0, len(plain), 16)):
        return None
    return b''.join(plain[i + 4:i + 16] for i in range(0, len(plain), 16))


def user_entry(user_id: str, nick: str, guild: str, grade, category: Optional[str] = None) -> bytes:
    """ID16 + nick12 [+ grupo: 1 byte 0 ou 20 bytes] + guild8 + u16 grade (0x1011 lista / 0x3001 / 0x4001)."""
    w = fixed(user_id, 16) + fixed(nick, 12)
    if category is not None:
        w += fixed(category, 20) if category else b'\0'
    return w + fixed(guild, 8) + struct.pack('<H', int(grade or 0) & 0xFFFF)


def wide(text: str) -> bytes:
    """wchar[20] do v584 (nick, guild)."""
    return (text or '').encode('utf-16-le')[:40].ljust(40, b'\0')


def ext16(grade) -> bytes:
    """ext16 do v584 para quem não mandou o próprio: u16 grade mostrada, u16 grade, 12 x 0xFF (como o .gme monta)."""
    g = int(grade or 0) & 0xFFFF
    return struct.pack('<HH', g, g) + b'\xFF' * 12


def notice_body(items) -> bytes:
    """0x1FFE (cliente 0x4e8c00): u16 n (< 11) + n x (u8 tam + título, u8 tam + texto)."""
    body = bytearray(struct.pack('<H', min(len(items), 10)))
    for title, text in items[:10]:
        for part in (title, text):
            raw = str(part).encode('latin-1', errors='replace')[:255]
            body += bytes([len(raw)]) + raw
    return bytes(body)


class BuddySession:
    def __init__(self, server: 'BuddyServer', reader, writer):
        self.server, self.reader, self.writer = server, reader, writer
        self.peer = writer.get_extra_info('peername') or ('0.0.0.0', 0)
        self.nonce = struct.unpack('<I', os.urandom(4))[0]
        self.token = struct.unpack('<I', os.urandom(4))[0]
        self.user_id: Optional[str] = None
        self.nick, self.key = '', b''
        self.local = (b'\0' * 4, b'\0\0')   # IP do socket TCP e porta UDP de P2P, como o cliente mandou (ordem de rede)
        self.public: Optional[tuple] = None  # (ip 4 bytes, porta 2 bytes big-endian) vindo do UDP do token
        self.v584 = False
        self.ext16 = b''  # v584: 16 bytes que o próprio cliente mandou no login (repassados aos amigos)

    # layout por versão: Id 16 (TH/S1) ou 20 (v584); nick/guild latin-1 de 12/8 ou wchar[20]
    def uid(self, user_id: str) -> bytes:
        return fixed(user_id, 20 if self.v584 else 16)

    def read_uid(self, r: BinaryReader) -> str:
        return cstr(r.read_bytes(20 if self.v584 else 16))

    def nick_bytes(self, nick: str) -> bytes:
        return wide(nick) if self.v584 else fixed(nick, 12)

    def log(self, msg: str):
        print(f"[{self.peer[0]}:{self.peer[1]}] {msg}")

    async def send(self, cmd: int, body: bytes = b''):
        self.log(f"SEND>> CD={cmd:04X} {body.hex(' ').upper()}")
        self.writer.write(packet(cmd, body))
        await self.writer.drain()

    def state_entry(self, viewer: 'BuddySession') -> bytes:
        public = self.public or (self.local[0] if self.local[0] != b'\0' * 4 else _ip_bytes(self.peer[0]), self.local[1])
        return viewer.uid(self.user_id) + b'\x01' + public[0] + public[1] + self.local[0] + self.local[1]

    async def run(self):
        self.log("conectou")
        try:
            while header := await self.reader.readexactly(4):
                size, cmd = struct.unpack('<HH', header)
                body = await self.reader.readexactly(max(size - 4, 0))
                self.log(f"RECV<< CD={cmd:04X} {body.hex(' ').upper()}")
                try:
                    await self.server.dispatch(self, cmd, body)
                except (PacketError, struct.error, IndexError) as e:
                    self.log(f"Pacote mal formado 0x{cmd:04X}: {e}")
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            await self.server.disconnect(self)
            self.writer.close()
            self.log("desconectou")


def _ip_bytes(ip: str) -> bytes:
    try:
        return bytes(int(p) for p in ip.split('.'))
    except ValueError:
        return b'\0' * 4


class BuddyServer:
    def __init__(self, repository, crypto: Optional[CryptoManager] = None, notice=None):
        self.repo = repository
        self.notice = notice or []  # config buddy_server.notice: [[título, texto], ...] (até 10), mandado no login
        self.crypto = crypto or CryptoManager(STATIC_KEY)
        self.online: Dict[str, BuddySession] = {}

    async def handle(self, reader, writer):
        await BuddySession(self, reader, writer).run()

    async def dispatch(self, s: BuddySession, cmd: int, body: bytes):
        if cmd == SVC_KEEPALIVE:
            return
        if cmd == SVC_PRECREDENTIAL:
            # TH/S1 só aceitam 4 bytes e o v584 só 8: cada um ignora o outro
            await s.send(RET_PRECREDENTIAL, struct.pack('<I', s.nonce))
            return await s.send(RET_PRECREDENTIAL, struct.pack('<II', s.nonce, V584_FEATURES))
        if cmd == SVC_LOGIN:
            return await (self.login_v584(s, body) if len(body) == V584_LOGIN_SIZE else self.login(s, body))
        if s.user_id is None:
            return s.log(f"0x{cmd:04X} antes do login, ignorado")
        handler = {
            SVC_ADD_BUDDY: self.add_buddy, SVC_REMOVE_BUDDY: self.remove_buddy, SVC_GROUP_BUDDY: self.group_buddy,
            SVC_RENAME_GROUP: self.rename_group, SVC_USER_STATE: self.user_state, SVC_SEARCH: self.search,
            SVC_TUNNEL: self.tunnel, SVC_SAVE_PACKET: self.save_packet, SVC_SAVE_PACKET_ACK: self.save_packet_ack,
            SVC_SMS: self.sms,
        }.get(cmd)
        if handler is None:
            return s.log(f"0x{cmd:04X} sem handler")
        await handler(s, BinaryReader(body))

    # ---- sessão ----
    async def login(self, s: BuddySession, body: bytes):
        if len(body) != 0x50:
            return await s.send(RET_LOGIN, struct.pack('<H', BAD_SIZE))
        user_id = cstr(self.crypto.decrypt(body[0:16]))  # [16:32] o original decifra e ignora
        user = await self.repo.get_user(user_id)
        if user is None:
            return await s.send(RET_LOGIN, struct.pack('<H', NOT_FOUND))
        plain = None
        if user:
            password = user['Password'] or ''
            # cliente direto guarda a senha pura; via NyxLauncher, md5(senha) em hex [12:32] (como no login do game)
            for candidate in (password, hashlib.md5(password.encode('latin-1')).hexdigest()[12:32]):
                key = self.crypto.derive_key(user_id, candidate, struct.pack('<I', s.nonce))
                data = decrypt_blocks(self.crypto, key, body[32:80])
                if data and data[4:4 + len(candidate)] == candidate.encode('latin-1'):  # memcmp do original (0x40f090)
                    plain, s.key = data, key
                    break
        if plain is None:
            s.log(f"Login recusado: {user_id!r}")
            return await s.send(RET_LOGIN, struct.pack('<H', BAD_PASSWORD))
        if not VERSION_FIRST <= struct.unpack_from('<I', plain)[0] <= VERSION_LAST:
            return await s.send(RET_LOGIN, struct.pack('<H', BAD_VERSION))
        await self.finish_login(s, user, plain)

    async def login_v584(self, s: BuddySession, body: bytes):
        """0x1010 do v584: AES estático(Id[0:16]) + AES estático(Id[16:20], u32 nonce, 8 de lixo) + 11 blocos de sessão
        (u32 versão 0x1B, senha[20] vazia, IP, porta UDP, nick wchar[20], guild wchar[20], ext16, lixo)."""
        head = self.crypto.decrypt(body[0:32])
        user_id = cstr(head[0:20])
        user = await self.repo.get_user(user_id)
        if user is None:
            return await s.send(RET_LOGIN, struct.pack('<H', NOT_FOUND))
        key = self.crypto.derive_key(user_id, '', struct.pack('<I', s.nonce))  # o Buddy2.dll sempre usa senha vazia
        plain = decrypt_blocks(self.crypto, key, body[32:V584_LOGIN_SIZE])
        if plain is None or head[20:24] != struct.pack('<I', s.nonce):
            s.log(f"Login v584 recusado (cifra): {user_id!r}")
            return await s.send(RET_LOGIN, struct.pack('<H', BAD_PASSWORD))
        if struct.unpack_from('<I', plain)[0] != V584_VERSION:
            return await s.send(RET_LOGIN, struct.pack('<H', BAD_VERSION))
        # sem senha: só entra quem está logado no game server agora, vindo do mesmo IP
        if await self.repo.game_session_ip(user['Id']) != _ip_bytes(s.peer[0]):
            s.log(f"Login v584 recusado: {user_id!r} sem sessão no game a partir de {s.peer[0]}")
            return await s.send(RET_LOGIN, struct.pack('<H', BAD_PASSWORD))
        s.v584, s.key, s.ext16 = True, key, plain[0x6E:0x7E]
        await self.finish_login(s, user, plain)

    async def finish_login(self, s: BuddySession, user, plain: bytes):
        if (old := self.online.get(user['Id'])) is not None and old is not s:
            old.user_id = None  # sessão antiga não avisa saída por cima da nova
            await old.send(NTF_CLOSE_CONNECTION, struct.pack('<H', 0))
            old.writer.close()
        s.user_id, s.nick = user['Id'], user['Nickname'] or ''
        s.local = (plain[0x18:0x1C], plain[0x1C:0x1E])
        self.online[s.user_id] = s
        s.log(f"Login {s.user_id} ({s.nick}), versão 0x{struct.unpack_from('<I', plain)[0]:X}")

        buddies = await self.repo.get_buddies(s.user_id)
        if s.v584:
            # 0x1012 com a lista ANTES do 0x1011: o 0x1011 entrega ao jogo o que já chegou e limpa as listas
            for i in range(0, len(buddies), V584_LIST_MAX):
                part = buddies[i:i + V584_LIST_MAX]
                await s.send(RET_BUDDY_LIST, struct.pack('<H', len(part)) + b''.join(self.entry_v584(b['Buddy'], b) for b in part))
            await s.send(RET_LOGIN, struct.pack('<HI', OK, s.token))
        else:
            body = struct.pack('<HI', OK, s.token) + fixed(s.nick, 12) + fixed(user['Guild'], 8)
            body += struct.pack('<HH', int(user['TotalGrade'] or 0) & 0xFFFF, len(buddies))
            previous = None
            for b in buddies:  # categoria só quando muda (lista ordenada por Category); senão 1 byte 0
                category = b['Category'] or ''
                body += user_entry(b['Buddy'], b['Nickname'], b['Guild'], b['TotalGrade'], category if category != previous else '')
                previous = category
            await s.send(RET_LOGIN, body)
        if buddies:
            await s.send(NTF_USER_STATE, self.states([b['Buddy'] for b in buddies], s))
        await self.deliver_saved(s)
        if self.notice and not s.v584:  # o v584 não mostra o 0x1FFE (sink vazio)
            await s.send(NTF_NOTICE, notice_body(self.notice))
        await self.notify_watchers(s.user_id, online=True)

    def entry_v584(self, user_id: str, u) -> bytes:
        """Amigo no 0x1012 / 0x3001 do v584: Id20, nick wchar[20], guild wchar[20], ext16, ext32 (zeros)."""
        online = self.online.get(user_id)
        ext = online.ext16 if online is not None and online.v584 else ext16(u['TotalGrade'])
        return fixed(user_id, 20) + wide(u['Nickname']) + wide(u['Guild']) + ext + b'\0' * 32

    async def disconnect(self, s: BuddySession):
        if s.user_id and self.online.get(s.user_id) is s:
            del self.online[s.user_id]
            await self.notify_watchers(s.user_id, online=False)

    async def udp_token(self, token: int, addr) -> bool:
        """O cliente manda o token do 0x1011 por UDP (o original ecoa): dali sai o endereço público do P2P.
        Se for diferente do declarado no login, avisa 0x101F e reavisa os amigos com o endereço novo."""
        s = next((x for x in self.online.values() if x.token == token), None)
        if s is None:
            return False
        public = (_ip_bytes(addr[0]), struct.pack('>H', addr[1]))
        if public == s.public:
            return True
        s.public = public
        s.log(f"UDP público {addr[0]}:{addr[1]}")
        if public != s.local:
            await s.send(NTF_VIP_IPPORT, public[0] + public[1])
        await self.notify_watchers(s.user_id, online=True)
        return True

    def states(self, ids, viewer: BuddySession) -> bytes:
        body = bytearray(struct.pack('<H', len(ids)))
        for user_id in ids:
            s = self.online.get(user_id)
            body += s.state_entry(viewer) if s else viewer.uid(user_id) + b'\0'
        return bytes(body)

    async def notify_watchers(self, user_id: str, online: bool):
        """Avisa (0x3FFF) quem tem user_id na lista e está conectado: é a resposta do servidor ao login/saída dele."""
        for watcher in await self.repo.buddy_of(user_id):
            if (w := self.online.get(watcher)) is not None:
                entry = self.states([user_id], w) if online else struct.pack('<H', 1) + w.uid(user_id) + b'\0'
                await w.send(NTF_USER_STATE, entry)

    # ---- lista ----
    async def add_buddy(self, s: BuddySession, r: BinaryReader):
        # v584: Id20 + ext32[32] + u16 (o .gme manda 0); sem grupo
        buddy_id = s.read_uid(r)
        category = '' if s.v584 else cstr(r.read_bytes(20))
        echo = 0
        if s.v584:
            r.read_bytes(32)
            echo = r.read_uint16()
        buddy = await self.repo.get_user(buddy_id) if buddy_id.lower() != s.user_id.lower() else None
        if buddy is None:
            return await s.send(RET_ADD_BUDDY, struct.pack('<H', NOT_FOUND))
        current = await self.repo.get_buddies(s.user_id)
        # já na lista: o original responde 0x51 e o cliente ignora; aqui responde OK para a tela sempre mostrar
        if not any(b['Buddy'].lower() == buddy['Id'].lower() for b in current):
            if len(current) >= MAX_BUDDIES:
                return await s.send(RET_ADD_BUDDY, struct.pack('<H', LIST_FULL))
            await self.repo.add(s.user_id, buddy['Id'], category)
        if s.v584:
            reply = self.entry_v584(buddy['Id'], buddy) + struct.pack('<H', echo)
        else:
            reply = user_entry(buddy['Id'], buddy['Nickname'], buddy['Guild'], buddy['TotalGrade'])
        await s.send(RET_ADD_BUDDY, struct.pack('<H', OK) + reply)
        await s.send(NTF_USER_STATE, self.states([buddy['Id']], s))

    async def remove_buddy(self, s: BuddySession, r: BinaryReader):
        buddy_id = s.read_uid(r)
        ok = await self.repo.remove(s.user_id, buddy_id)
        await s.send(RET_REMOVE_BUDDY, struct.pack('<H', OK if ok else NOT_FOUND) + s.uid(buddy_id))

    # shortcut: grupos (0x3004/0x3006) só no layout TH/S1; o .gme do v584 não chama esses métodos do Buddy2.dll
    async def group_buddy(self, s: BuddySession, r: BinaryReader):
        count = r.read_uint16()
        if count > MAX_BUDDIES:
            return await s.send(RET_GROUP_BUDDY, struct.pack('<H', TOO_MANY))
        ids = [s.read_uid(r) for _ in range(count)]
        await self.repo.set_category(s.user_id, ids, cstr(r.read_bytes(20)))
        await s.send(RET_GROUP_BUDDY, struct.pack('<H', OK))

    async def rename_group(self, s: BuddySession, r: BinaryReader):
        old, new = cstr(r.read_bytes(20)), cstr(r.read_bytes(20))
        await self.repo.rename_category(s.user_id, old, new)
        await s.send(RET_RENAME_GROUP, struct.pack('<H', OK))

    async def user_state(self, s: BuddySession, r: BinaryReader):
        await s.send(NTF_USER_STATE, self.states([s.read_uid(r)], s))

    async def search(self, s: BuddySession, r: BinaryReader):
        nick, user_id = cstr(r.read_bytes(12)), cstr(r.read_bytes(8))
        offset, count = r.read_uint16(), r.read_uint16()
        if count > MAX_BUDDIES:
            return await s.send(RET_SEARCH, struct.pack('<H', TOO_MANY))
        found = await self.repo.search(nick, user_id, offset, count)
        body = struct.pack('<HH', OK, len(found)) + b''.join(
            user_entry(u['Id'], u['Nickname'], u['Guild'], u['TotalGrade']) for u in found)
        await s.send(RET_SEARCH, body)

    # ---- mensagens ----
    async def route(self, s: BuddySession, dest: str, code: int, data: bytes, store: bool):
        """Entrega como 0x2021 se o destino está conectado; senão guarda (packet) para o próximo login."""
        if (target := self.online.get(dest)) is not None:
            if target.v584 != s.v584:  # Id e texto do P2P têm formatos diferentes: o outro cliente não entenderia
                return s.log(f"0x{code:04X} para {dest} ignorado: versões de Buddy diferentes")
            await target.send(NTF_TUNNEL_PACKET, target.uid(s.user_id) + target.nick_bytes(s.nick) + struct.pack('<HH', code, len(data)) + data)
        elif store and await self.repo.get_user(dest):  # shortcut: não sabe a versão de quem está offline; guardado entre versões chega ilegível
            await self.repo.save_packet(dest, s.user_id, code, data)

    async def tunnel(self, s: BuddySession, r: BinaryReader):
        storable = r.read_uint8()
        code, size = r.read_uint16(), r.read_uint16()
        data = r.read_bytes(size)
        dests = [s.read_uid(r) for _ in range(min(r.read_uint16(), MAX_TUNNEL_DEST))]
        for dest in dests:
            await self.route(s, dest, code, data, store=bool(storable))

    async def save_packet(self, s: BuddySession, r: BinaryReader):
        plain = decrypt_blocks(self.crypto, s.key, r.read_bytes())
        if plain is None:
            return s.log("0x2000 com cifra inválida")
        p = BinaryReader(plain)
        dest, code, size = s.read_uid(p), p.read_uint16(), p.read_uint16()
        await self.route(s, dest, code, p.read_bytes(size), store=True)

    async def sms(self, s: BuddySession, r: BinaryReader):
        plain = decrypt_blocks(self.crypto, s.key, r.read_bytes())
        if plain is None:
            return await s.send(RET_SMS, struct.pack('<H', FAIL))
        p = BinaryReader(plain)
        dest, size = s.read_uid(p), p.read_uint16()
        await self.route(s, dest, V584_SMS if s.v584 else P2P_SMS, p.read_bytes(size), store=True)
        await s.send(RET_SMS, struct.pack('<H', OK))

    async def deliver_saved(self, s: BuddySession):
        saved = await self.repo.get_packets(s.user_id)
        for i in range(0, len(saved), MAX_SAVED_PER_PACKET):
            await self.send_saved(s, saved[i:i + MAX_SAVED_PER_PACKET])

    async def send_saved(self, s: BuddySession, saved):
        body = bytearray(struct.pack('<H', len(saved)))
        for m in saved:
            when = to_datetime(m['Time'])
            stamp = int(when.timestamp()) if when else int(time.time())
            data = bytes(m['Body'] or b'')
            body += struct.pack('<I', m['SerialNo']) + s.uid(m['Sender']) + s.nick_bytes(m['Nickname'])
            body += struct.pack('<IHH', stamp, int(m['Code']) & 0xFFFF, len(data)) + data
        await s.send(NTF_SAVE_PACKET, encrypt_blocks(self.crypto, s.key, bytes(body)))

    async def save_packet_ack(self, s: BuddySession, r: BinaryReader):
        await self.repo.delete_packets(s.user_id, [r.read_uint32() for _ in range(r.read_uint16())])


class BuddyUdp(asyncio.DatagramProtocol):
    def __init__(self, server: BuddyServer):
        self.server = server

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if len(data) == 4:
            asyncio.ensure_future(self._token(data, addr))

    async def _token(self, data, addr):
        if await self.server.udp_token(struct.unpack('<I', data)[0], addr):
            self.transport.sendto(data, addr)  # eco, como o original (0x402278)
