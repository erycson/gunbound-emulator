import struct

class BinaryReader:
    def __init__(self, data: bytes = b""):
        self._buffer = data
        self._pos = 0

    def read_int8(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<b' if le else '>b'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 1
        return value

    def read_uint8(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<B' if le else '>B'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 1
        return value

    def read_int16(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<h' if le else '>h'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 2
        return value

    def read_uint16(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<H' if le else '>H'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 2
        return value

    def read_int32(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<i' if le else '>i'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 4
        return value

    def read_uint32(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<I' if le else '>I'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 4
        return value

    def read_int64(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<q' if le else '>q'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 8
        return value

    def read_uint64(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<Q' if le else '>Q'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 8
        return value

    def read_int(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<i' if le else '>i'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 4
        return value

    def read_short(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<h' if le else '>h'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 2
        return value

    def read_float(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<f' if le else '>f'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 4
        return value

    def read_double(self, pos=None, le=True):
        p = self._pos if pos is None else pos
        fmt = '<d' if le else '>d'
        value = struct.unpack_from(fmt, self._buffer, p)[0]
        if pos is None:
            self._pos += 8
        return value

    def read_byte(self, pos=None):
        p = self._pos if pos is None else pos
        value = self._buffer[p]
        if pos is None:
            self._pos += 1
        return value
    
    def read_bytes(self, length=None, pos=None):
        p = self._pos if pos is None else pos
        length = length if length is not None else self.size() - p
        b = self._buffer[p:p+length]
        if pos is None:
            self._pos += length
        return b

    def read_string(self, length, pos=None, encoding='utf-8'):
        p = self._pos if pos is None else pos
        raw = self._buffer[p:p+length]
        s = raw.rstrip(b'\x00').decode(encoding)
        if pos is None:
            self._pos += length
        return s

    def getvalue(self):
        return bytes(self._buffer)

    def to_hex(self, from_index=0, to_index=None):
        to_index = to_index if to_index is not None else len(self._buffer)
        return ' '.join(f'{b:02X}' for b in self._buffer[from_index:to_index])

    def size(self):
        return len(self._buffer)

    def seek(self, pos):
        self._pos = pos

    def tell(self):
        return self._pos

class BinaryWriter:
    def __init__(self):
        self._buffer: bytearray = bytearray()
        self._pos: int = 0

    def write_int8(self, value, pos=None, le=True, insert=False):
        fmt = '<b' if le else '>b'
        b = struct.pack(fmt, int(value))
        return self.write_bytes(b, 1, pos, insert=insert)

    def write_uint8(self, value, pos=None, le=True, insert=False):
        fmt = '<B' if le else '>B'
        b = struct.pack(fmt, int(value))
        return self.write_bytes(b, 1, pos, insert=insert)

    def write_int16(self, value, pos=None, le=True, insert=False):
        fmt = '<h' if le else '>h'
        b = struct.pack(fmt, int(value))
        return self.write_bytes(b, 2, pos, insert=insert)

    def write_uint16(self, value, pos=None, le=True, insert=False):
        fmt = '<H' if le else '>H'
        b = struct.pack(fmt, int(value))
        return self.write_bytes(b, 2, pos, insert=insert)

    def write_int32(self, value, pos=None, le=True, insert=False):
        fmt = '<i' if le else '>i'
        b = struct.pack(fmt, int(value))
        return self.write_bytes(b, 4, pos, insert=insert)

    def write_uint32(self, value, pos=None, le=True, insert=False):
        fmt = '<I' if le else '>I'
        b = struct.pack(fmt, int(value))
        return self.write_bytes(b, 4, pos, insert=insert)

    def write_int64(self, value, pos=None, le=True, insert=False):
        fmt = '<q' if le else '>q'
        b = struct.pack(fmt, int(value))
        return self.write_bytes(b, 8, pos, insert=insert)

    def write_uint64(self, value, pos=None, le=True, insert=False):
        fmt = '<Q' if le else '>Q'
        b = struct.pack(fmt, int(value))
        return self.write_bytes(b, 8, pos, insert=insert)

    def write_short(self, value, pos=None, le=True, insert=False):
        fmt = '<h' if le else '>h'
        b = struct.pack(fmt, int(value))
        return self.write_bytes(b, 2, pos, insert=insert)

    def write_float(self, value, pos=None, le=True, insert=False):
        fmt = '<f' if le else '>f'
        b = struct.pack(fmt, float(value))
        return self.write_bytes(b, 4, pos, insert=insert)

    def write_double(self, value, pos=None, le=True, insert=False):
        fmt = '<d' if le else '>d'
        b = struct.pack(fmt, float(value))
        return self.write_bytes(b, 8, pos, insert=insert)

    def write_byte(self, value, pos=None, insert=False):
        b = bytes([value])
        return self.write_bytes(b, 1, pos, insert=insert)

    def write_char(self, value, pos=None, insert=False):
        return self.write_byte(ord(value), pos, insert)

    def write_string(self, value, length=None, pos=None, encoding='latin-1', insert=False):
        b = value.encode(encoding)
        length = length if length is not None else len(b)
        b = b[:length] + b'\x00' * (length - len(b))
        return self.write_bytes(b, length, pos, insert=insert)

    def write_bytes(self, data: bytearray | bytes, length=None, pos=None, insert=False):
        if isinstance(data, bytearray):
            data = bytes(data)

        if length is not None:
            data = data + b'\0' * (length - len(data))
        else:
            length = len(data)

        if pos is None:
            self._buffer[self._pos:self._pos+length] = data
            self._pos += length
        else:
            if insert:
                self._buffer[pos:pos] = data  # insere deslocando o resto
            else:
                # Expand buffer if needed
                if pos + length > len(self._buffer):
                    self._buffer.extend(b'\x00' * (pos + length - len(self._buffer)))
                self._buffer[pos:pos+length] = data
        return self

    def getraw(self, from_index=0, to_index=None) -> bytearray:
        buffer = bytearray(len(self._buffer))
        buffer[:] = self._buffer
        return buffer
    
    def getvalue(self, from_index=0, to_index=None) -> bytes:
        to_index = to_index if to_index is not None else len(self._buffer)
        return bytes(self._buffer[from_index:to_index]) 
    
    def size(self) -> int:
        return len(self._buffer)

    def to_hex(self, from_index=0, to_index=None) -> str:
        to_index = to_index if to_index is not None else len(self._buffer)
        return ' '.join(f'{b:02X}' for b in self._buffer[from_index:to_index])

    def seek(self, pos: int):
        self._pos = pos

    def tell(self) -> int:
        return self._pos

    def to_reader(self):
        return BinaryReader(self.getvalue())
    
    def clone(self):
        writer = BinaryWriter()
        writer.write_bytes(self.getraw())
        return writer
