from typing import Iterable

def _rotl32(x: int, n: int) -> int:
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF

class SHA1:
    __slots__ = ("_h0","_h1","_h2","_h3","_h4","_unprocessed","_length")
    def __init__(self) -> None:
        self._h0 = 0x67452301
        self._h1 = 0xEFCDAB89
        self._h2 = 0x98BADCFE
        self._h3 = 0x10325476
        self._h4 = 0xC3D2E1F0
        self._unprocessed = b""
        self._length = 0

    def update(self, data: bytes) -> "SHA1":
        if not data:
            return self
        self._length += len(data)
        data = self._unprocessed + data
        blocks = (len(data) // 64) * 64
        for i in range(0, blocks, 64):
            self._process_chunk(data[i:i+64])
        self._unprocessed = data[blocks:]
        return self

    # -------- Transform padrão RFC (não usamos aqui) ----------
    def _process_chunk(self, chunk: bytes) -> None:
        # Mantido para referência; vamos sobrescrever na subclasse
        raise NotImplementedError

    def _finalize(self) -> bytes:
        ml_bits = self._length * 8
        pad = b"\x80" + b"\x00" * ((56 - (self._length + 1) % 64) % 64)
        self.update(pad + ml_bits.to_bytes(8, "big"))
        # Saída canônica (não usada pela subclasse custom)
        return (
            self._h0.to_bytes(4, "big") +
            self._h1.to_bytes(4, "big") +
            self._h2.to_bytes(4, "big") +
            self._h3.to_bytes(4, "big") +
            self._h4.to_bytes(4, "big")
        )

    def digest(self) -> bytes:
        clone = self.__class__()  # importante: respeita a subclasse
        clone._h0, clone._h1, clone._h2, clone._h3, clone._h4 = self._h0, self._h1, self._h2, self._h3, self._h4
        clone._unprocessed = self._unprocessed
        clone._length = self._length
        return clone._finalize()

    def hexdigest(self) -> str:
        return self.digest().hex()

class SHA1WithoutROTL(SHA1):
    """Transform que NÃO faz o ROTL1 no schedule (igual ao seu binário),
       e Final que emite H0..H3 em little-endian (16 bytes)."""
    def _process_chunk(self, chunk: bytes) -> None:
        assert len(chunk) == 64
        # 16 palavras little-endian iniciais
        w = [int.from_bytes(chunk[i:i+4], "big") for i in range(0, 64, 4)]
        # >>> DIFERENÇA CRÍTICA: schedule sem ROTL1 <<<
        for i in range(16, 80):
            w.append((w[i-3] ^ w[i-8] ^ w[i-14] ^ w[i-16]) & 0xFFFFFFFF)

        a, b, c, d, e = self._h0, self._h1, self._h2, self._h3, self._h4

        for i in range(80):
            if i < 20:
                f = (b & c) | (~b & d); k = 0x5A827999
            elif i < 40:
                f = b ^ c ^ d;          k = 0x6ED9EBA1
            elif i < 60:
                f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDC
            else:
                f = b ^ c ^ d;          k = 0xCA62C1D6
            temp = (_rotl32(a, 5) + f + e + k + w[i]) & 0xFFFFFFFF
            a, b, c, d, e = temp, a, _rotl32(b, 30), c, d

        self._h0 = (self._h0 + a) & 0xFFFFFFFF
        self._h1 = (self._h1 + b) & 0xFFFFFFFF
        self._h2 = (self._h2 + c) & 0xFFFFFFFF
        self._h3 = (self._h3 + d) & 0xFFFFFFFF
        self._h4 = (self._h4 + e) & 0xFFFFFFFF

    def _finalize(self) -> bytes:
        # Padding padrão (igual ao seu SHA1_Final)
        ml_bits = self._length * 8
        pad = b"\x80" + b"\x00" * ((56 - (self._length + 1) % 64) % 64)
        self.update(pad + ml_bits.to_bytes(8, "big"))
        # >>> Emite H0..H3 em LITTLE-ENDIAN (16 bytes) <<<
        return (
            self._h0.to_bytes(4, "little") +
            self._h1.to_bytes(4, "little") +
            self._h2.to_bytes(4, "little") +
            self._h3.to_bytes(4, "little")
        )

# Como usar
# m = b"aaaa" + b"bbbb" + b"\x29\x00\x00\x00"
# d16 = SHA1_Mode3().update(m).digest().hex().upper()
# print("DERIVED16:", d16)