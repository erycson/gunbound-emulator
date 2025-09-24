import sys
import asyncio
from gunbound.managers import ConfigManager, DatabaseManager, CryptoManager
from gunbound.game.managers import ClientManager, MonitorManager
from gunbound.game_server import GameServer
import gunbound.game.protocol # Garante o registro automático dos protocolos

async def main(index = 0):
    # Inicializa os Managers
    config = ConfigManager.initialize("config.yml")
    if not (0 <= index < len(config['gameservers'])):
        raise ValueError(f"Configurações para o servidor {index} não encontradas")
    
    await DatabaseManager.initialize(config['database']['uri'])
    CryptoManager.initialize(config['crypto'])
    ClientManager.initialize()

    # Inicia o servidor
    config = config['gameservers'][index]
    game = GameServer(index, config)
    MonitorManager.initialize(game, config).start()
    await game.start()

if __name__ == "__main__":
    index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    asyncio.run(main(index))
