from __future__ import annotations
import time
import socket
import asyncio
from typing import TYPE_CHECKING
from asyncio import CancelledError, Task
from gunbound.base.enums import Feature
from gunbound.game_server import GameServer
from gunbound.util import BinaryReader, BinaryWriter, UDPFutureProtocol
from dependency_injector.providers import Configuration

if TYPE_CHECKING:
    from gunbound.game.managers import ClientManager, RoomManager
    from gunbound.game_server import GameServer
    from gunbound.repository import ServerRepository

class MonitorManager:
    def __init__(
        self,
        server: 'GameServer',
        config: Configuration,
        client_manager: 'ClientManager',
        room_manager: 'RoomManager',
        server_repository: 'ServerRepository'
    ):
        self.server = server
        self.config = config
        self.client_manager = client_manager
        self.room_manager = room_manager
        self.server_repository = server_repository
        self.task_broker: Task = None
        self.task_user_count: Task = None
        self.transport = None

    async def start(self):
        self.task_broker = asyncio.create_task(self.udp_listener())
        self.task_user_count = asyncio.create_task(self.user_count_monitor())

    async def udp_listener(self):
        transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
            lambda: UDPFutureProtocol(),
            local_addr=(self.config['host'], self.config['port'])
        )

        while True:
            try:
                response, addr = await protocol.response_future

                reader = BinaryReader(response)
                print(f"UDP-RECV [FROM={addr[0]}:{addr[1]} Accept=1]: {reader.to_hex()}")

                if reader.size() == 4:
                    await self.udp_proc_initial_udp_recv(transport, addr, reader)
                    continue

                if not self.udp_allowed(addr[0]):  # 0x402950 do original: IP fora da lista é ignorado
                    print(f"UDP-DROP [FROM={addr[0]}:{addr[1]}] IP fora de udp_allow")
                    continue

                length = reader.read_uint16()
                if length != reader.size() or reader.size() < 4:
                    continue
                
                match reader.read_uint16():
                    case 0xF000:
                        await self.udp_get_state(transport, addr, reader)
                    case 0xF010 if length == 10:
                        await self.udp_force_logout(reader)
                    case 0xF020 if length == 0x18:
                        await self.udp_notify(reader, 0x1050)
                    case 0xF030 if length == 8:
                        await self.udp_reload_cash(reader)
            except CancelledError:
                protocol.response_future.cancel()
                transport.close()
                break
            finally:
                protocol.response_future = asyncio.Future()

    async def user_count_monitor(self):
        interval = self.config['stats_interval']

        await asyncio.sleep(interval)
        while True:
            start_time = time.time()
            
            await self.server_repository.insert_user_count(
                self.config['broker']['version'],
                int.from_bytes(socket.inet_aton(self.config['broker']['host']), 'little'),
                self.config['broker']['port'],
                self.client_manager.size()
            )

            elapsed_time = time.time() - start_time
            sleep_time = max(0, interval - elapsed_time)
            await asyncio.sleep(sleep_time)

    async def stop(self):
        self.task_broker.cancel()
        self.task_user_count.cancel()

        try:
            await self.task_broker
            await self.task_user_count
        except CancelledError:
            pass

    def is_running(self):
        return self.task_broker and not self.task.done()

    async def udp_get_state(self, transport: asyncio.DatagramTransport, addr, reader: BinaryReader):
        index = reader.read_uint32()
        if index != self.server.index:
            return

        writer = BinaryWriter()
        writer.write_uint16(23)                         # Size
        writer.write_uint16(0xF001)                     # Command
        writer.write_uint32(self.server.index)          # ServerIndex
        writer.write_uint16(self.room_manager.size())   # Rooms
        writer.write_uint16(self.client_manager.size()) # UsersOnline
        writer.write_uint16(self.config['users_max'])   # UsersMax
        writer.write_int16(self.config['grade_max'])    # LevelMin (pode ser q seja só 1 byte)
        writer.write_uint16(0)                          # Desconhecido
        writer.write_int16(self.config['grade_min'])    # LevelMax (pode ser q seja só 1 byte)
        writer.write_uint16(0)                          # Desconhecido
        writer.write_uint8(1 if self.server.features & Feature.AVATAR_ENABLED else 0) # Avatar Enabled

        transport.sendto(writer.getvalue(), addr)

    async def udp_proc_initial_udp_recv(self, transport: asyncio.DatagramTransport, addr, reader: BinaryReader):
        """
        Função que basicamente verifica se o cliente possui o mesmo valor da sequencia.
        Ainda não sei o motivo dessa verificação, mas presumo que é para testar a conexão UDP com o GameServer.
        """
        sequence = reader.read_uint32()

        # Chave = token do 0x1012 (+2). Original 0x42b670: uma vez por sessão, guarda o endereço observado e, se diferir
        # do IP/porta UDP declarados no 0x1010, manda 0x101F (u32 ip + u16 porta em ordem de rede) antes do eco.
        conn = next((c for c in self.client_manager.sessions.values() if c.data.get('token') == sequence), None)
        if conn is not None and 'udp_seen' in conn.data:
            pass  # já conferido: só o eco
        elif conn is not None:
            conn.data['udp_seen'] = addr
            observed = socket.inet_aton(addr[0]) + addr[1].to_bytes(2, 'big')
            ip, port = conn.data.get('net') or (0, 0)
            if observed != int(ip).to_bytes(4, 'little') + int(port).to_bytes(2, 'big'):
                from gunbound.game.protocol.base import Packet
                from gunbound.game.protocol.enums import ServerPacket
                await conn.on_send(Packet.new(ServerPacket.SRV_UDP_ADDRESS).raw(observed))
        else:
            async with self.client_manager.lock:
                if sequence != self.client_manager.rand.current_value:
                    return

        # Uso o BinaryWriter apenas para padronizar o tratamento de dados
        writer = BinaryWriter()
        writer.write_uint32(sequence)

        transport.sendto(writer.getvalue(), addr)
    def udp_allowed(self, ip: str) -> bool:
        import ipaddress
        nets = self.config.get('udp_allow') if hasattr(self.config, 'get') else None
        try:
            return any(ipaddress.ip_address(ip) in ipaddress.ip_network(n, strict=False)
                       for n in (nets or ['127.0.0.1/32']))
        except ValueError:
            return False

    def find_by_user_no(self, user_no: int):
        """0x410af0 do original: procura a conexão pelo número do usuário (u32 após len/cmd)."""
        return next((c for c in self.client_manager.sessions.values()
                     if c.data.get('profile', {}).get('Id') == user_no), None)

    async def udp_force_logout(self, reader: BinaryReader):
        """0xF010 (0x42b7b0): avisa 0x1FFF rtc 2 e derruba a conexão."""
        from gunbound.game.protocol.base import Packet
        conn = self.find_by_user_no(reader.read_uint32())
        if conn is not None:
            await conn.on_send(Packet.new(0x1FFF, rtc=2))
            await conn.close()

    async def udp_notify(self, reader: BinaryReader, cmd: int):
        """0xF020 GiftTransfer (0x42b820): só envia 0x1050 vazio; o cliente busca o presente."""
        from gunbound.game.protocol.base import Packet
        conn = self.find_by_user_no(reader.read_uint32())
        if conn is not None:
            await conn.on_send(Packet.new(cmd))

    async def udp_reload_cash(self, reader: BinaryReader):
        """0xF030 ReloadCash (0x42b850): relê o cash do banco e reenvia 0x6101."""
        from gunbound.game.protocol.cash import CashRecv
        conn = self.find_by_user_no(reader.read_uint32())
        if conn is not None:
            await CashRecv(conn, BinaryReader(b'')).process()
