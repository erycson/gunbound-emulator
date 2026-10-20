import abc
import asyncio
import struct
from typing import Optional, Type
from gunbound.base.protocol.recv import BasePackageRecv
from gunbound.util.binary_buffer import BinaryReader, BinaryWriter
from gunbound.util.dump import dump

class BasePackageFactory(abc.ABC):
    registry: dict[int, Type[BasePackageRecv]] = {}

    @classmethod
    def register(cls, type_code):
        def decorator(subclass):
            cls.registry[type_code] = subclass
            return subclass
        return decorator

    @classmethod
    async def from_data(cls, command, conn, buf: BinaryReader, table: Optional[dict] = None):
        # table: opcodes da fase do game server (gunbound/game/phase.py); sem ela (broker), o catálogo inteiro
        handler: Optional[Type[BasePackageRecv]] = (cls.registry if table is None else table).get(command)
        if not handler:
            print(f"[{conn.addr}] Pacote desconhecido: 0x{command:04X} (len={buf.size()})")
            dump(buf.getvalue())
            return

        data = handler(conn, buf)
        data.log_command(conn)
        asyncio.create_task(cls._safe_process(command, conn, data))

    @staticmethod
    async def _safe_process(command, conn, data: BasePackageRecv):
        # Pacote curto ou com campo inválido (struct.error / PacketError / enum ValueError) não derruba o servidor.
        try:
            await data.process()
        except (struct.error, ValueError) as e:
            print(f"[{conn.addr}] Pacote mal formado 0x{command:04X}: {type(e).__name__}: {e}")

    @classmethod
    @abc.abstractmethod
    async def process(cls, buf: BinaryReader):
        pass