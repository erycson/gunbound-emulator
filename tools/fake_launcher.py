"""Imita o NyxLauncher no broker, para testes: 0x1310 login -> 0x3000 -> 0x4000.
Uso: .venv\\Scripts\\python tools\\fake_launcher.py [usuario=test] [--password X] [--host 127.0.0.1] [--port 8372]
A senha é pedida no terminal (não fica em arquivo). A chave vem do config.yml."""
import argparse, getpass, hashlib, os, random, socket, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import yaml
from gunbound.base.managers.crypto import CryptoManager

ap = argparse.ArgumentParser()
ap.add_argument('user', nargs='?', default='test')
ap.add_argument('--password')
ap.add_argument('--host', default='127.0.0.1')
ap.add_argument('--port', type=int, default=8372)
ap.add_argument('--game', default='Gunbound')
a = ap.parse_args()
pw = a.password or getpass.getpass('Senha: ')

cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), '..', 'config.yml'), encoding='utf-8'))
crypto = CryptoManager(cfg['crypto']['broker_key'])

# o launcher usa md5(senha) hex, caracteres [12:32], como senha
pw = hashlib.md5(pw.encode('latin-1')).hexdigest()[12:32]
user = a.user.encode('latin-1')[:16]
session = struct.pack('<I', random.getrandbits(15))  # launcher usa rand()

block_a = crypto.encrypt(user.ljust(16, b'\0')) + crypto.encrypt(session.ljust(16, b'\0'))
key = crypto.derive_key(user.decode('latin-1'), pw, session)
plain = pw.encode('latin-1').ljust(20, b'\0') + struct.pack('<I', 0)  # senha[20] + versão
block_b = b''.join(crypto.encrypt(b'\0' * 4 + plain[i:i + 12], key) for i in (0, 12))

sent = 0
def send(cmd, body=b'', zero_seq=False):
    global sent
    n = 6 + len(body)
    seq = 0 if zero_seq else ((sent + n) * 0x43fd - 0x613d) & 0xFFFF
    if cmd != 0x4000:  # igual ao launcher: o 0x4000 não entra no contador
        sent += n
    s.sendall(struct.pack('<HHH', n, seq, cmd) + body)
    print(f'>> {cmd:04X} {body.hex(" ")}')

def read(n):
    b = b''
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            sys.exit('broker fechou a conexao')
        b += c
    return b

def recv():
    n, seq, cmd = struct.unpack('<HHH', read(6))
    body = read(n - 6) if n > 6 else b''
    code = struct.unpack_from('<H', body)[0] if len(body) >= 2 else None
    print(f'<< {cmd:04X} code={code} {body.hex(" ")}')
    return cmd, code

s = socket.create_connection((a.host, a.port), timeout=10)
send(0x1310, block_a + block_b, zero_seq=True)
cmd, code = recv()
if (cmd, code) != (0x1312, 0):
    sys.exit(f'login falhou (code={code})')
send(0x3000)
recv()
g = a.game.encode('latin-1')
send(0x4000, bytes([len(g)]) + g + struct.pack('<I', 0) + b'\x04test' + struct.pack('<III', 0, 0, 0), zero_seq=True)
cmd, code = recv()
print('OK: launcher abriria o jogo' if (cmd, code) == (0x4001, 0) else f'start game falhou (code={code})')
