"""Teste local (dois clientes no mesmo PC): o segundo não consegue a 8363 e informa a porta errada no login.
Pergunta ao Windows qual a porta UDP real do processo dono da conexão TCP. Só usado para 127.0.0.1."""
import ctypes, socket, sys
from ctypes import wintypes as w

class _TcpRow(ctypes.Structure):
    _fields_ = [('state', w.DWORD), ('laddr', w.DWORD), ('lport', w.DWORD), ('raddr', w.DWORD), ('rport', w.DWORD), ('pid', w.DWORD)]

class _UdpRow(ctypes.Structure):
    _fields_ = [('laddr', w.DWORD), ('lport', w.DWORD), ('pid', w.DWORD), ('created', ctypes.c_longlong),
                ('flags', ctypes.c_int), ('module', ctypes.c_ulonglong * 16)]

def _table(fn, row, cls):
    size = w.DWORD(0)
    fn(None, ctypes.byref(size), False, socket.AF_INET, cls, 0)
    buf = ctypes.create_string_buffer(size.value)
    if fn(buf, ctypes.byref(size), False, socket.AF_INET, cls, 0):
        return []
    n = w.DWORD.from_buffer(buf).value
    off = ctypes.sizeof(ctypes.c_longlong) if ctypes.alignment(row) == 8 else 4
    return list((row * n).from_buffer(buf, off))

def real_udp_port(tcp_peer_port: int) -> int | None:
    """Porta UDP mais antiga do processo cuja porta TCP local é tcp_peer_port (o socket do jogo nasce primeiro)."""
    if sys.platform != 'win32':
        return None
    ip = ctypes.windll.iphlpapi
    pid = next((r.pid for r in _table(ip.GetExtendedTcpTable, _TcpRow, 5) if socket.ntohs(r.lport & 0xFFFF) == tcp_peer_port), None)
    rows = [r for r in _table(ip.GetExtendedUdpTable, _UdpRow, 2) if pid and r.pid == pid]
    return socket.ntohs(min(rows, key=lambda r: r.created).lport & 0xFFFF) if rows else None
