import abc
from gunbound.util.binary_buffer import BinaryWriter

class BasePackageSend(abc.ABC):
    @abc.abstractmethod
    def get_buf(self) -> BinaryWriter:
        pass

    @abc.abstractmethod
    def log_command(self, conn):
        pass

