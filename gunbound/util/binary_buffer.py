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
    
    def read_bytes(self, length, pos=None):
        p = self._pos if pos is None else pos
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

    def to_hex(self):
        return ' '.join(f'{b:02X}' for b in self._buffer)

    def size(self):
        return len(self._buffer)

    def seek(self, pos):
        self._pos = pos

    def tell(self):
        return self._pos

class BinaryWriter:
    def __init__(self):
        self._buffer = bytearray()
        self._pos = 0

    def write_int8(self, value, pos=None, le=True, insert=False):
        fmt = '<b' if le else '>b'
        b = struct.pack(fmt, int(value))
        self._write_bytes(b, 1, pos, insert=insert)

    def write_uint8(self, value, pos=None, le=True, insert=False):
        fmt = '<B' if le else '>B'
        b = struct.pack(fmt, int(value))
        self._write_bytes(b, 1, pos, insert=insert)

    def write_int16(self, value, pos=None, le=True, insert=False):
        fmt = '<h' if le else '>h'
        b = struct.pack(fmt, int(value))
        self._write_bytes(b, 2, pos, insert=insert)

    def write_uint16(self, value, pos=None, le=True, insert=False):
        fmt = '<H' if le else '>H'
        b = struct.pack(fmt, int(value))
        self._write_bytes(b, 2, pos, insert=insert)

    def write_int32(self, value, pos=None, le=True, insert=False):
        fmt = '<i' if le else '>i'
        b = struct.pack(fmt, int(value))
        self._write_bytes(b, 4, pos, insert=insert)

    def write_uint32(self, value, pos=None, le=True, insert=False):
        fmt = '<I' if le else '>I'
        b = struct.pack(fmt, int(value))
        self._write_bytes(b, 4, pos, insert=insert)

    def write_int64(self, value, pos=None, le=True, insert=False):
        fmt = '<q' if le else '>q'
        b = struct.pack(fmt, int(value))
        self._write_bytes(b, 8, pos, insert=insert)

    def write_uint64(self, value, pos=None, le=True, insert=False):
        fmt = '<Q' if le else '>Q'
        b = struct.pack(fmt, int(value))
        self._write_bytes(b, 8, pos, insert=insert)

    def write_short(self, value, pos=None, le=True, insert=False):
        fmt = '<h' if le else '>h'
        b = struct.pack(fmt, int(value))
        self._write_bytes(b, 2, pos, insert=insert)

    def write_float(self, value, pos=None, le=True, insert=False):
        fmt = '<f' if le else '>f'
        b = struct.pack(fmt, float(value))
        self._write_bytes(b, 4, pos, insert=insert)

    def write_double(self, value, pos=None, le=True, insert=False):
        fmt = '<d' if le else '>d'
        b = struct.pack(fmt, float(value))
        self._write_bytes(b, 8, pos, insert=insert)

    def write_byte(self, value, pos=None, insert=False):
        b = bytes([value])
        self._write_bytes(b, 1, pos, insert=insert)

    def write_string(self, value, length, pos=None, encoding='utf-8', insert=False):
        b = value.encode(encoding)
        b = b[:length] + b'\x00' * (length - len(b))
        self._write_bytes(b, length, pos, insert=insert)

    def _write_bytes(self, b, length, pos, insert=False):
        if pos is None:
            self._buffer[self._pos:self._pos+length] = b
            self._pos += length
        else:
            if insert:
                self._buffer[pos:pos] = b  # insere deslocando o resto
            else:
                # Expand buffer if needed
                if pos + length > len(self._buffer):
                    self._buffer.extend(b'\x00' * (pos + length - len(self._buffer)))
                self._buffer[pos:pos+length] = b

    def getvalue(self):
        return bytes(self._buffer)
    
    def size(self):
        return len(self._buffer)

    def to_hex(self):
        return ' '.join(f'{b:02X}' for b in self._buffer)

    def seek(self, pos):
        self._pos = pos

    def tell(self):
        return self._pos

    def to_reader(self):
        return BinaryReader(self.getvalue())
