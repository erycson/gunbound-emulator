import asyncio
from gunbound.broker.managers import GameServerManager, ConfigManager, DatabaseManager
from gunbound.broker_server import BrokerServer
from gunbound.util.aes_cipher import AESCipher
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
    # Inicializa os Manganers
    config = ConfigManager.initialize("config.yml")
    await DatabaseManager.initialize(config['database']['uri'])
    manager = GameServerManager.initialize(config['gameservers'])
    manager.start_monitor()

    # Inicia o servidor de dump na porta 8360
    await asyncio.start_server(dump_handler(8360), '0.0.0.0', 8360) # GunBoundServ
    await asyncio.start_server(dump_handler(8382), '0.0.0.0', 8382) # BuddyCenter
    await asyncio.start_server(dump_handler(8352), '0.0.0.0', 8352) # BuddyServ
    # await asyncio.sleep(float('inf'))
    # Inicia o servidor
    crypto = AESCipher(config.get('crypto'))
    broker = BrokerServer(config['broker'], crypto)
    await broker.start()

if __name__ == "__main__":
    asyncio.run(main())
