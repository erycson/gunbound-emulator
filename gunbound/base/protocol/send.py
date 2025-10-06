import abc
from gunbound.util.binary_buffer import BinaryWriter

class BasePackageSend(abc.ABC):
    @abc.abstractmethod
    def log_command(self, conn):
        pass

    def get_buf(self) -> BinaryWriter:
        return self.buf

    def encrypt(self, conn) -> BinaryWriter:
        return self.buf
    
    def clone(self) -> 'BasePackageSend':
        return self.__class__(self.buf.clone())