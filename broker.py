import asyncio
import signal
from gunbound.base.managers import ConfigManager, DatabaseManager, CryptoManager
from gunbound.broker.managers import GameServerManager
from gunbound.broker_server import BrokerServer
from gunbound.util.dump import dump
import gunbound.broker.protocol # Garante o registro automático dos protocolos

async def save_data():
    # Implementar lógica de salvamento aqui
    # Por exemplo, salvar estados dos clientes, commit database, etc.
    print("Saving data...")
    # await DatabaseManager.save() or something
    pass

def dump_handler(port):
    async def loop(reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"[{port}] Dump server: conexão de {addr}")

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                dump(data)
        except Exception as e:
            print(f"Erro no dump server: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    return loop

async def main():
    # Inicializa os Managers
    config = ConfigManager.initialize("config.yml")
    database = await DatabaseManager.initialize(config['database']['uri'])
    CryptoManager.initialize(config['crypto']['broker_key'])
    manager = GameServerManager.initialize(config['gameservers'])
    await manager.start()

    # Servidores dump
    # await asyncio.start_server(dump_handler(8352), '0.0.0.0', 8352)  # BuddyServ
    # await asyncio.start_server(dump_handler(8382), '0.0.0.0', 8382)  # BuddyCenter

    broker = BrokerServer(config['broker'])
    await broker.start()

    shutdown_event = asyncio.Event()

    async def shutdown():
        await manager.stop()
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
