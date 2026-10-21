import sys, os
from gunbound.util import filelog
_cfg = next((a for a in sys.argv[1:] if a.endswith(('.yml', '.yaml'))), 'config.yml')
_idx = next((a for a in sys.argv[1:] if a.isdigit()), '')  # game.py [arquivo.yml] [índice]: log separado por servidor
filelog.start(('game' if _cfg == 'config.yml' else 'game-' + os.path.splitext(os.path.basename(_cfg))[0]) + (f'-{_idx}' if _idx else ''))
import signal
import asyncio
from gunbound.game.containers import Container
import gunbound.game.protocol # Garante o registro automático dos protocolos

async def main():
    container = Container()
    container.wire(packages=["gunbound.game.protocol"])
    
    database = container.database()
    await database.connect()

    monitor = container.monitor()
    await monitor.start()

    server = container.server()
    await server.start()
    idle_rooms = asyncio.create_task(container.rooms().idle_loop())  # sala ociosa (L8)
    
    shutdown_event = asyncio.Event()
    async def shutdown():
        idle_rooms.cancel()
        await monitor.stop()
        await server.stop()
        # tarefas de cliente presas numa consulta: terminar antes de fechar o banco, senão o aiosqlite responde
        # com o loop já fechado ("Event loop is closed")
        rest = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for t in rest:
            t.cancel()
        await asyncio.gather(*rest, return_exceptions=True)
        await database.disconnect()
        print("GameServer parado")
        
    loop = asyncio.get_running_loop()
    def signal_handler(signum, frame):
        loop.call_soon_threadsafe(shutdown_event.set)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await shutdown_event.wait()
    await shutdown()  # aqui, e não numa task: o asyncio.run cancelaria a task no meio

if __name__ == "__main__":
    asyncio.run(main())
