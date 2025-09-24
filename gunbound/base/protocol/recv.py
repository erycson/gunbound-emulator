import abc
from gunbound.util.binary_buffer import BinaryReader

class BasePackageRecv(abc.ABC):
    @abc.abstractmethod
    async def process(self, buf: BinaryReader):
        pass

    @abc.abstractmethod
    def log_command(self, conn):
        pass
    
