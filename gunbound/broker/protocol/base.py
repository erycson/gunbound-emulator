# lib/protocol/base.py
import abc
import asyncio
from gunbound.util.binary_buffer import BinaryReader
from gunbound.broker.exceptions import UnknownPacketError

class BasePackageFactory(abc.ABC):
    registry = {}

    @classmethod
    def register(cls, type_code):
        def decorator(subclass):
            cls.registry[type_code] = subclass
            return subclass
        return decorator

    @classmethod
    async def from_data(cls, command, conn, buf: BinaryReader):
        handler = cls.registry.get(command)
        if not handler:
            raise UnknownPacketError(f"Comando não implementado: {command:#04x}", buf)
        
        # Cria a instância do pacote e chama o método process
        pacote = handler(conn)
        asyncio.create_task(pacote.process(buf))

    @classmethod
    @abc.abstractmethod
    async def process(cls, buf: BinaryReader):
        pass

class BasePackageRecv(abc.ABC):
    @abc.abstractmethod
    async def process(self, buf: BinaryReader):
        pass
    
class BasePackageSend(abc.ABC):
    @abc.abstractmethod
    def to_bytes(self):
        pass