import yaml
from databases import Database
from dependency_injector import containers, providers
from gunbound.base.managers import CryptoManager
from gunbound.broker.managers import MonitorManager
from gunbound.broker_server import BrokerServer
from gunbound.repository import ServerRepository

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    with open("config.yml", "r", encoding="utf-8") as f:
        config.from_dict(yaml.load(f, Loader=yaml.FullLoader), required=True)
    crypto = providers.Singleton(CryptoManager, key=config.crypto.broker_key())
    database = providers.Singleton(Database, url=config.database.uri())

    server_repository = providers.Factory(ServerRepository, db=database)
    
    login_strategy = providers.Singleton(
        config.broker.strategies.login(),
        db=database,
        crypto=crypto
    )

    broker = providers.Singleton(BrokerServer, config=config.broker, server_repository=server_repository)
    monitor = providers.Singleton(MonitorManager, config=config, server_repository=server_repository)
