import signal
import asyncio
from gunbound.game.containers import Container
import gunbound.game.protocol # Garante o registro automático dos protocolos

async def main():
    container = Container()
    
    database = container.database()
    await database.connect()

    monitor = container.monitor()
    await monitor.start()

    server = container.server()
    await server.start()
    
    shutdown_event = asyncio.Event()
    async def shutdown():
        await monitor.stop()
        await server.stop()
        await database.disconnect()
        print("GameServer parado")
        
    def signal_handler(signum, frame):
        asyncio.get_running_loop().create_task(shutdown())
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await shutdown_event.wait()

if __name__ == "__main__":
    asyncio.run(main())
