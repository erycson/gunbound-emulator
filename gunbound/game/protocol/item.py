from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
from gunbound.game import phase
if TYPE_CHECKING:
    from gunbound.repository import InventoryRepository
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_ITEM.value)
@inject
class ItemRecv(BasePackageRecv):
    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        inventory_repository: 'InventoryRepository' = Provide['inventory_repository'],
    ):
        self.buf = buf
        self.conn = conn
        self.inventory_repository = inventory_repository

    async def process(self):
        chest = await self.inventory_repository.get_chest(self.conn.data['profile']['Id'])
        self.conn.data.setdefault('avatar', [int(c['Item']) for c in chest if c['Wearing']][:8])  # roupa vestida antes, para o bloco da sala
        # power user como no original (0x42e7cc): ter o SuperUserItem com prazo ainda válido
        super_item = self.conn.server.config.get('super_user_item')
        self.conn.data['power_user'] = any(int(c['Item']) == super_item and c['Expire'] is not None and c['Expire'] > 0 for c in chest)
        await self.conn.on_send(ItemResp.success(chest, phase.of(self.conn), self.conn.data.get('client_version', 0)))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_ITEM.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class ItemResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, chest, layout, client_version=0):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_ITEM)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint16(len(chest))

        for item in reversed(chest):
            buf.write_uint32(item['No'])
            buf.write_uint32(item['Item'])
            buf.write_uint8(int(item['Wearing']))
            buf.write_char(item['Acquisition'])

            if item['Expire'] is None:
                buf.write_uint8(0)
            else:
                buf.write_uint8(1)
                buf.write_uint32(int(item['Expire']))
            active = item['Expire'] is None or item['Expire'] > 0
            buf.write_uint8(active)  # flag: o cliente só lê o u32 quando é 1 (TH 0x41199c); antes o Volume ia sempre e desalinhava
            if active:
                buf.write_uint32(item['Volume'])
            buf.write_uint8(1)  # Desconhecido
            buf.write_uint32(int(item['PlaceOrder'] or 0))
            buf.write_bytes(layout.chest_tail(item, client_version))

        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X}] {self.buf.to_hex(6)}")