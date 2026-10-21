from gunbound.util import filelog
filelog.start('broker')
import asyncio
import signal
from gunbound.broker.containers import Container
# from gunbound.util.dump import dump
import gunbound.broker.protocol # Garante o registro automático dos protocolos

async def main():
    container = Container()
    container.wire(packages=["gunbound.broker.protocol"])

    database = container.database()
    await database.connect()

    monitor = container.monitor()
    await monitor.start()

    # Servidores dump
    # await asyncio.start_server(dump_handler(8352), '0.0.0.0', 8352)  # BuddyServ

    broker = container.broker()
    await broker.start()

    shutdown_event = asyncio.Event()
    async def shutdown():
        await monitor.stop()
        await broker.stop()
        # tarefas de cliente presas numa consulta: terminar antes de fechar o banco, senão o aiosqlite responde
        # com o loop já fechado ("Event loop is closed")
        rest = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for t in rest:
            t.cancel()
        await asyncio.gather(*rest, return_exceptions=True)
        await database.disconnect()
        print("BrokerServer parado")

    loop = asyncio.get_running_loop()
    def signal_handler(signum, frame):
        loop.call_soon_threadsafe(shutdown_event.set)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await shutdown_event.wait()
    await shutdown()  # aqui, e não numa task: o asyncio.run cancelaria a task no meio

if __name__ == "__main__":
    asyncio.run(main())
