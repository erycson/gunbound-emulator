import abc
from gunbound.util.binary_buffer import BinaryReader, BinaryWriter
from gunbound.util.dump import dump

class BasePackageSend(abc.ABC):
    @abc.abstractmethod
    def get_buf(self) -> BinaryWriter:
        pass

    @abc.abstractmethod
    def log_command(self, conn):
        pass

