from __future__ import annotations
from typing import TYPE_CHECKING
from dependency_injector.wiring import Provide, inject
from gunbound.base.protocol import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.util.binary_buffer import BinaryWriter, BinaryReader
from gunbound.game.protocol.enums import ClientPacket, ServerPacket, ServerCode
if TYPE_CHECKING:
    from gunbound.repository import InventoryRepository
    from gunbound.game.client import ClientConnection

@BasePackageFactory.register(ClientPacket.CLI_GOLD.value)
@inject
class GoldRecv(BasePackageRecv):

    def __init__(
        self,
        conn: 'ClientConnection',
        buf: BinaryReader,
        inventory_repository: 'InventoryRepository' = Provide['inventory_repository']
    ):
        self.buf = buf
        self.conn = conn
        self.inventory_repository = inventory_repository

    async def process(self):
        money = await self.inventory_repository.get_money(self.conn.data['profile']['Id'])
        await self.conn.on_send(GoldResp.success(money))

    def log_command(self, conn):
        cmd = ClientPacket.CLI_GOLD.value
        seq = conn.expected_client_checksum(self.buf.size())
        print(f"RECV<< [SS={conn.server.id:08X} SQ={seq:04X} CD={cmd:04X}]")

class GoldResp(BasePackageSend):
    def __init__(self, buf: BinaryWriter):
        self.buf = buf 

    @classmethod
    def success(cls, money: int):
        buf = BinaryWriter()
        buf.write_uint16(ServerPacket.SRV_GOLD)
        buf.write_uint16(ServerCode.SRV_OK)
        buf.write_uint32(money)

        return cls(buf)
    
    def log_command(self, conn):
        reader = self.buf.to_reader()
        checksum = reader.read_uint16(pos=2)
        cmd = reader.read_uint16(pos=4)
        rtc = reader.read_uint16(pos=6)

        print(f"SEND>> [SS={conn.server.id:08X} SQ={checksum:04X} CD={cmd:04X} RTC={rtc:04X}] {self.buf.to_hex(8)}")