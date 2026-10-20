"""Offline S2 transport codec. Not a GameGuard answer generator or validator.

Constants are read from the exact original S2 server, never executed here.
Addresses: init 4432B0, block 443180/443250, query 4430C0, answer 443120.
"""
import hashlib
import struct
from pathlib import Path

SERVER_SHA256 = '7e954d735e380ddc757d1ab20bd4b9341b5bfb55ceb8a9c5dd60dbabb1052e57'
MASK = 0xffffffff

class Codec:
    def __init__(self, server):
        raw = Path(server).read_bytes()
        if hashlib.sha256(raw).hexdigest() != SERVER_SHA256:
            raise ValueError('Unsupported original server SHA-256')
        # Minimal bounded PE32 RVA reader; no third-party/native dependency.
        nt, = struct.unpack_from('<I', raw, 0x3c)
        if raw[:2] != b'MZ' or raw[nt:nt+4] != b'PE\0\0':
            raise ValueError('Invalid PE')
        machine, count = struct.unpack_from('<HH', raw, nt+4)
        optional_size, = struct.unpack_from('<H', raw, nt+20)
        magic, = struct.unpack_from('<H', raw, nt+24)
        imagebase, = struct.unpack_from('<I', raw, nt+52)
        if machine != 0x14c or magic != 0x10b:
            raise ValueError('Expected PE32 i386')
        sections = nt+24+optional_size
        def read(va, n):
            rva = va-imagebase
            for i in range(count):
                size, start, rawsize, offset = struct.unpack_from('<4I', raw, sections+i*40+8)
                if start <= rva and rva+n <= start+rawsize:
                    result = raw[offset+rva-start:offset+rva-start+n]
                    if len(result) == n:
                        return result
            raise ValueError('RVA outside file-backed sections')
        self.p = list(struct.unpack('<18I', read(0x456354, 72)))
        self.s = list(struct.unpack('<1024I', read(0x45639c, 4096)))
        key = read(0x46a0fc, 10)
        for i in range(18):
            word = 0
            for j in range(4):
                word = (word << 8) | key[(i*4+j) % len(key)]
            self.p[i] ^= word
        left = right = 0
        for table in (self.p, self.s):
            for i in range(0, len(table), 2):
                left, right = self.block(left, right)
                table[i:i+2] = [left, right]

    def f(self, x):
        s = self.s
        return ((((s[x >> 24] + s[256+((x >> 16)&255)]) & MASK)
                  ^ s[512+((x >> 8)&255)]) + s[768+(x&255)]) & MASK

    def block(self, left, right, decrypt=False):
        p = self.p
        for i in (range(17, 1, -1) if decrypt else range(16)):
            t = left ^ p[i]
            left, right = self.f(t) ^ right, t
        return right ^ p[0 if decrypt else 17], left ^ p[1 if decrypt else 16]

    @staticmethod
    def words(body):
        if len(body) != 16:
            raise ValueError('CSAuth2 transport requires exactly 16 bytes')
        return list(struct.unpack('<4I', body))

    def encode_query(self, body):
        a = self.words(body)
        a[0] ^= 0x00fd3a9d
        a[1] ^= 0x9d2db902
        a[0], a[2] = self.block(a[0], a[2])
        a[2] ^= 0x0064d84a
        a[3] ^= 0xf0f4c802
        a[1], a[3] = self.block(a[1], a[3])
        return struct.pack('<4I', *a)

    def decode_answer(self, body):
        a = self.words(body)
        a[1], a[3] = self.block(a[1], a[3], True)
        a[2] ^= 0x0b64d24a
        a[3] ^= 0xf674c8b9
        a[0], a[2] = self.block(a[0], a[2], True)
        a[0] ^= 0x0afd349d
        a[1] ^= 0x9d28b918
        return struct.pack('<4I', *a)

    def decode_query(self, body):
        """Inverse of S2 0x4430C0, before any protocol-DLL decryption."""
        a = self.words(body)
        a[1], a[3] = self.block(a[1], a[3], True)
        a[2] ^= 0x0064d84a
        a[3] ^= 0xf0f4c802
        a[0], a[2] = self.block(a[0], a[2], True)
        a[0] ^= 0x00fd3a9d
        a[1] ^= 0x9d2db902
        return struct.pack('<4I', *a)
