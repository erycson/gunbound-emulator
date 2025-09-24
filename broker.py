import asyncio
from gunbound.managers import ConfigManager, DatabaseManager, CryptoManager
from gunbound.broker.managers import GameServerManager
from gunbound.broker_server import BrokerServer
from gunbound.util.dump import dump
import gunbound.broker.protocol # Garante o registro automático dos protocolos

async def dump_handler(port):
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
    await DatabaseManager.initialize(config['database']['uri'])
    CryptoManager.initialize(config['crypto'])
    manager = GameServerManager.initialize(config['gameservers'])
    manager.start_monitor()

    await asyncio.start_server(dump_handler(8352), '0.0.0.0', 8352) # BuddyServ
    await asyncio.start_server(dump_handler(8382), '0.0.0.0', 8382) # BuddyCenter

    # Inicia o servidor
    broker = BrokerServer(config['broker'])
    await broker.start()

if __name__ == "__main__":
    asyncio.run(main())
