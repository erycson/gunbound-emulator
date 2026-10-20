"""TEST ONLY. Not configurable as a production validator or native qualification."""
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gunbound.game.ggauth50_helper import DLL_SHA256, read_frame, write_frame

mode = sys.argv[1]
generation = 'a' * 32
while True:
    try:
        req = read_frame(sys.stdin.buffer)
    except EOFError:
        break
    res = dict(request_id=req['request_id'], generation=generation, ok=True)
    cmd = req['command']
    if cmd == 'hello':
        res.update(contract=1, protocol=0x10050, dll_sha256=DLL_SHA256,
                   architecture='x86', native=True, minimum_version=2003010101)
    elif mode == 'crash':
        sys.exit(7)
    elif mode == 'hang':
        time.sleep(60)
    elif mode == 'oversize':
        sys.stdout.buffer.write(struct.pack('<I', 4097))
        sys.stdout.buffer.flush()
        time.sleep(60)
    elif mode == 'truncated':
        sys.stdout.buffer.write(struct.pack('<I', 100) + b'{')
        sys.stdout.buffer.flush()
        sys.exit(0)
    elif mode == 'bad_id':
        res['request_id'] += 1
    elif mode == 'restart':
        res['generation'] = 'b' * 32
    elif cmd == 'create_session':
        res['session_id'] = 'c' * 32
    elif cmd == 'query':
        res.update(code=0, exchange_id=1, internal='00' * 12 + '50000100')
    elif cmd == 'check':
        res.update(code=0, accepted=True)
    write_frame(sys.stdout.buffer, res)
