"""Envia UDP administrativo ao GameServer. Uso: python tools/udp_admin.py logout|gift|cash <user_no> [host] [porta]"""
import socket, struct, sys
cmd, no = sys.argv[1], int(sys.argv[2])
host, port = (sys.argv[3] if len(sys.argv) > 3 else '127.0.0.1'), int(sys.argv[4]) if len(sys.argv) > 4 else 8360
code, size = {'logout': (0xF010, 10), 'gift': (0xF020, 0x18), 'cash': (0xF030, 8)}[cmd]
pkt = struct.pack('<HHI', size, code, no).ljust(size, b'\0')
socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(pkt, (host, port))
