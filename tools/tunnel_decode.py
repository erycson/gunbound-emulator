"""
Decifra a captura do túnel (tunnel_log do game server) para ler o P2P da partida (docs/Bots.md).
Frame (cliente v584 0x461740): u16 hdr (len & 0x3fff | 0x8000 | 0x4000 confiável), u8 seq, u8 soma do cifrado,
AES-128-ECB(payload). Payload = u16 tipo + campos. Chave = u16 server_id + "comsik" + u16 room_id + d222eafaee3a,
server_id = o índice do servidor na lista do broker (0x1102).
  python tools/tunnel_decode.py tunnel-capture.jsonl [server_id]
"""
import json
import struct
import sys
from Crypto.Cipher import AES

TAIL = bytes.fromhex('d222eafaee3a')
NAMES = {0xc400: 'tiro', 0xc409: 'tiro SS', 0x8403: 'tiro item', 0x8402: 'posição', 0x8005: 'mover', 0x4001: 'virar',
         0x4005: 'troca tiro', 0x4006: 'mira', 0xc401: 'item', 0xc412: 'passa turno', 0xc302: 'fim de turno',
         0xc303: 'sync/novo turno', 0xc413: 'resp. passa', 0xc40b: 'fim (4410)', 0x8500: 'morte/saída',
         0x4002: 'chat', 0x4003: 'chat time', 0x4004: 'provocação', 0x8100: 'ready', 0x4002 | 0: 'chat'}


def key(server_id: int, room_id: int) -> bytes:
    return struct.pack('<H', server_id) + b'comsik' + struct.pack('<H', room_id) + TAIL


def decode(frame: bytes, k: bytes) -> tuple[int, int, bytes]:
    hdr, seq = struct.unpack_from('<HB', frame)
    cipher = frame[4:(hdr & 0x3fff)]
    plain = AES.new(k, AES.MODE_ECB).decrypt(cipher[:len(cipher) // 16 * 16])
    return hdr, seq, plain


def detail(kind: int, body: bytes) -> str:
    """Campos já conhecidos (cliente v584): C302 inicial (0x4e9b2a) e morte C304 (0x48293b)."""
    if kind == 0xc302 and len(body) >= 13 and body[0] == 0x0f:
        turn, x, floor = struct.unpack_from('<3I', body, 1)
        return f"  [inicial: turno {turn}, x {x}, chão {floor}{' = sem chão' if floor >= 9000 else ''}]"
    if kind == 0xc304 and len(body) >= 5:
        cause, killer = struct.unpack_from('<IB', body)
        return f"  [morte: causa {cause:#x}{' (autochecagem)' if cause & 0x10 else ''}, matador {killer}]"
    return ''


assert 'x 0, chão 10000' in detail(0xc302, bytes.fromhex('0f 00000000 00000000 10270000'))


def main(path: str, server_id: int = 0):
    rows = [json.loads(line) for line in open(path, encoding='utf-8')]
    t0 = rows[0]['t'] if rows else 0
    for r in rows:
        frame = bytes.fromhex(r['hex'])
        hdr, seq, plain = decode(frame, key(server_id, r['room']))
        kind = struct.unpack_from('<H', plain)[0] if len(plain) >= 2 else -1
        print(f"{r['t'] - t0:7.2f} {'J' if r['playing'] else 'S'} {r['from']}->{r['to']} hdr={hdr:04X} seq={seq:3d} "
              f"tipo={kind:04X} {NAMES.get(kind, ''):14} {plain[2:].hex(' ')}{detail(kind, plain[2:])}")


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
