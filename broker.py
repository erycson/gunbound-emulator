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
    # await asyncio.start_server(dump_handler(8382), '0.0.0.0', 8382)  # BuddyCenter

    broker = container.broker()
    await broker.start()

    shutdown_event = asyncio.Event()
    async def shutdown():
        await monitor.stop()
        await broker.stop()
        await database.disconnect()
        print("BrokerServer parado")

    def signal_handler(signum, frame):
        asyncio.get_running_loop().create_task(shutdown())
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await shutdown_event.wait()

if __name__ == "__main__":
    asyncio.run(main())
