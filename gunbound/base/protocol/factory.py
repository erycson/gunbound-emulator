import abc
import asyncio
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
    async def from_data(cls, command, conn, buf: BinaryReader):
        handler: Optional[Type[BasePackageRecv]] = cls.registry.get(command)
        if not handler:
            print(f"[{conn.addr}] Pacote desconhecido: 0x{command:04X} (len={buf.size()})")
            dump(buf.getvalue())
            return

        data = handler(conn, buf)
        data.log_command(conn)
        asyncio.create_task(data.process())

    @classmethod
    @abc.abstractmethod
    async def process(cls, buf: BinaryReader):
        pass