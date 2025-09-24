import asyncio
from gunbound.managers import ConfigManager, DatabaseManager
from gunbound.broker.managers import GameServerManager
from gunbound.broker_server import BrokerServer
from gunbound.util.aes_cipher import AESCipher
from gunbound.util.dump import dump
import gunbound.broker.protocol # Garante o registro automático dos protocolos

async def main():
    # Inicializa os Managers
    config = ConfigManager.initialize("config.yml")
    await DatabaseManager.initialize(config['database']['uri'])
    manager = GameServerManager.initialize(config['gameservers'])
    manager.start_monitor()

    # Inicia o servidor
    crypto = AESCipher(config.get('crypto'))
    broker = BrokerServer(config['broker'], crypto)
    await broker.start()

if __name__ == "__main__":
    asyncio.run(main())
