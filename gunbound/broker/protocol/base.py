# lib/protocol/base.py
import abc
import asyncio
from typing import Optional, Type
from gunbound.util.binary_buffer import BinaryReader, BinaryWriter
from gunbound.broker.exceptions import UnknownPacketError

class BasePackageRecv(abc.ABC):
    @abc.abstractmethod
    async def process(self, buf: BinaryReader):
        pass

    @abc.abstractmethod
    def log_command(self, conn):
        pass
    
class BasePackageSend(abc.ABC):
    @abc.abstractmethod
    def get_buf(self) -> BinaryWriter:
        pass

    @abc.abstractmethod
    def log_command(self, conn):
        pass

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
            raise UnknownPacketError(f"Comando não implementado: {command:#04x}", buf)
        
        # Cria a instância do pacote e chama o método process
        data = handler(conn, buf)
        data.log_command(conn)
        asyncio.create_task(data.process())

    @classmethod
    @abc.abstractmethod
    async def process(cls, buf: BinaryReader):
        pass