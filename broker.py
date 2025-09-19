import asyncio
from gunbound.broker_server import BrokerServer
from gunbound.util.aes_cipher import AESCipher
from gunbound.broker.managers.config import ConfigManager
from gunbound.broker.managers.database import DatabaseManager
import gunbound.broker.protocol # Garante o registro automático dos protocolos

async def main():
    # Inicializa o ConfigManager e DatabaseManager
    config = ConfigManager.initialize("config.yml")
    await DatabaseManager.initialize(config['database']['uri'])

    # Inicia o servidor
    crypto = AESCipher(config.get('crypto'))
    broker = BrokerServer(config['broker'], crypto)
    await broker.start()

if __name__ == "__main__":
    asyncio.run(main())
