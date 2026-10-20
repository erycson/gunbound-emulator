"""Copia tudo que sai no console (stdout/stderr) para logs/<nome>-<data>.log sem bloquear o servidor:
o print só enfileira; uma thread grava e dá flush a cada lote, então nada se perde se o processo cair."""
import atexit
import os
import queue
import sys
import threading
import time

_STOP = object()


class _Tee:
    def __init__(self, stream, q):
        self.stream, self.q = stream, q

    def write(self, text):
        self.q.put(text)
        return self.stream.write(text)

    def __getattr__(self, name):
        return getattr(self.stream, name)


def start(name: str, folder: str = 'logs') -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.log")
    q: queue.Queue = queue.Queue()

    def writer():
        with open(path, 'a', encoding='utf-8', errors='replace') as f:
            while True:
                item = q.get()
                batch = [item]
                while not q.empty():
                    batch.append(q.get_nowait())
                stop = _STOP in batch
                f.write(''.join(b for b in batch if b is not _STOP))
                f.flush()
                if stop:
                    return

    thread = threading.Thread(target=writer, name='filelog', daemon=True)
    thread.start()
    sys.stdout, sys.stderr = _Tee(sys.stdout, q), _Tee(sys.stderr, q)

    def stop():
        q.put(_STOP)
        thread.join(timeout=5)
    atexit.register(stop)
    return path
