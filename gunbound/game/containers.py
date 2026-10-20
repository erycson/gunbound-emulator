import sys
import yaml
from gunbound.base.database import Database
from dependency_injector import containers, providers
from gunbound.base.managers import CryptoManager
from gunbound.game.client import ClientConnection
from gunbound.game.room import Room
from gunbound.game.managers import ClientManager, MonitorManager, ChannelManager, RoomManager, GrandPrixManager
from gunbound.game_server import GameServer
from gunbound.repository import ServerRepository, UserRepository, InventoryRepository, RecordsRepository, GrandPrixRepository

# game.py [arquivo.yml] [índice]: arquivo padrão config.yml; índice padrão = server_index do arquivo (ou 0)
args = sys.argv[1:]
config_file = args.pop(0) if args and args[0].endswith(('.yml', '.yaml')) else "config.yml"
with open(config_file, "r", encoding="utf-8") as f:
    config_data = yaml.load(f, Loader=yaml.FullLoader)
index = int(args[0]) if args else int(config_data.get('server_index', 0))

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    config.from_dict(config_data, required=True)
    config_gameserver = config.gameservers()[index]
    
    crypto = providers.Singleton(CryptoManager, key=config.crypto.game_key())
    database = providers.Singleton(Database, url=config.database.uri())
    server_repository = providers.Factory(ServerRepository, db=database)
    user_repository = providers.Factory(UserRepository, db=database)
    inventory_repository = providers.Factory(InventoryRepository, db=database)
    records_repository = providers.Factory(RecordsRepository, db=database)
    grandprix_repository = providers.Factory(GrandPrixRepository, db=database)

    client_factory = providers.Factory(ClientConnection)
    room_factory = providers.Factory(Room)

    clients = providers.Singleton(ClientManager, client_factory=client_factory.provider)
    channels = providers.Singleton(ChannelManager)
    server = providers.Singleton(
        GameServer,
        index=index,
        config=config_gameserver,
        channel_manager=channels,
        client_manager=clients,
        server_repository=server_repository,
    )
    rooms = providers.Singleton(
        RoomManager,
        server=server,
        config=config_gameserver,
        room_factory=room_factory.provider,
    )
    grandprix = providers.Singleton(
        GrandPrixManager,
        config=config_gameserver,
        room_manager=rooms,
        grandprix_repository=grandprix_repository,
    )
    monitor = providers.Singleton(
        MonitorManager,
        server=server,
        config=config_gameserver,
        client_manager=clients,
        room_manager=rooms,
        server_repository=server_repository,
    )

    client_factory.add_attributes(
        server=server,
        client_manager=clients,
        crypto_manager=crypto,
        user_repository=user_repository,
        server_repository=server_repository
    )
    room_factory.add_attributes(room_manager=rooms)
