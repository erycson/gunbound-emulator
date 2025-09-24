import asyncio
from gunbound.managers import ConfigManager, DatabaseManager
from gunbound.game.managers import SessionManager, MonitorManager
from gunbound.game_server import GameServer
from gunbound.util.aes_cipher import AESCipher
from gunbound.util.dump import dump
import gunbound.game.protocol # Garante o registro automático dos protocolos

async def main():
    # Inicializa os Managers
    config = ConfigManager.initialize("config.yml")
    index = 0
    game_config = config['gameservers'][index]

    await DatabaseManager.initialize(config['database']['uri'])
    SessionManager.initialize()

    # Inicia o servidor
    crypto = AESCipher(config.get('crypto'))
    game = GameServer(game_config, crypto)

    monitor = MonitorManager.initialize(game, game_config)
    monitor.start()

    await game.start_game()

if __name__ == "__main__":
    asyncio.run(main())
