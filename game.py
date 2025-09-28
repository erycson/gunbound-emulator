import sys
import signal
import asyncio
from gunbound.base.managers import ConfigManager, DatabaseManager, CryptoManager
from gunbound.game.managers import ClientManager, MonitorManager
from gunbound.game_server import GameServer
import gunbound.game.protocol # Garante o registro automático dos protocolos

async def main(index = 0):
    # Inicializa os Managers
    config = ConfigManager.initialize("config.yml")
    if not (0 <= index < len(config['gameservers'])):
        raise ValueError(f"Configurações para o servidor {index} não encontradas")
    
    database = await DatabaseManager.initialize(config['database']['uri'])
    CryptoManager.initialize(config['crypto']['game_key'])
    ClientManager.initialize()

    # Inicia o servidor
    config = config['gameservers'][index]
    game = GameServer(index, config)
    await game.start()

    monitor = MonitorManager.initialize(game, config)
    await monitor.start()

    shutdown_event = asyncio.Event()

    async def shutdown():
        await monitor.stop()
        await game.stop()
        await database.disconnect()
        print("GameeServer parado")
        
    def signal_handler(signum, frame):
        asyncio.get_running_loop().create_task(shutdown())
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await shutdown_event.wait()

if __name__ == "__main__":
    index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    asyncio.run(main(index))
