from gunbound.util.binary_buffer import BinaryReader

class UnknownPacketError(ValueError):
    """
    Exceção personalizada para erros de parsing de buffer.
    Inclui referência ao buffer problemático.
    """
    def __init__(self, message, buf: BinaryReader):
        super().__init__(message)
        self.buf = buf

    def getcmd(self):
        return self.buf.read_uint16(2)
