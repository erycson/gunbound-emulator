from __future__ import annotations
from typing import TYPE_CHECKING
import socket
import asyncio
from gunbound.repository import ranking
from gunbound.game import anticheat, phase
from asyncio import Task, CancelledError, StreamReader, StreamWriter
from dependency_injector.providers import Configuration
if TYPE_CHECKING:
    from gunbound.repository import ServerRepository
    from gunbound.game.managers import ClientManager, ChannelManager

# Tarefas de fundo que cada fase pode pedir em Phase.tasks
TASKS = {
    'ranking': lambda server, p: ranking.daily(server.server_repository.db, p.rank_rule),
}


class GameServer:
    def __init__(
        self,
        index: int,
        config: Configuration,
        channel_manager: 'ChannelManager',
        client_manager: 'ClientManager',
        server_repository: 'ServerRepository',
    ):
        self.id = id(self) & 0xFFFFFFFF
        self.index = index
        self.config = config
        self.task: Task = None
        self.channels = channel_manager
        self.clients = client_manager
        self.server_repository = server_repository
        self.features = self.calc_features(config)

    async def handler(self, reader: StreamReader, writer: StreamWriter):
        await self.clients.add(reader, writer)

    async def start(self):
        p = phase.PHASES[self.config.get('phase') or phase.DEFAULT]
        p.check(self.config)
        await self.check_db_version(self.config.get('phase') or phase.DEFAULT)
        provider, mode = anticheat.settings(self.config)  # required sem validador confirmado: não sobe
        if (self.config.get('anticheat') or {}).get('validator') in ('ggauth', 'ggauth50'):
            from gunbound.game.ggauth50 import initialize
            await initialize(self, self.config['anticheat'])
        print(f"[anticheat] {self.config['name']}: provider={provider} mode={mode}")
        # Fechar a janela não chama stop(); limpa sessões que sobraram da execução anterior
        await self.server_repository.delete_all_users(self.config['host'], self.config['port'])
        self.task = asyncio.create_task(self.tcp_listener())
        self.tasks = [asyncio.create_task(TASKS[name](self, p)) for name in p.tasks]
        await self.server_repository.insert_service_status(
            self.config['product_version'],
            int.from_bytes(socket.inet_aton(self.config['host']), 'little'),
            self.config['port'],
            'S'
        )

    async def check_db_version(self, name: str):
        """Avisa se o banco foi criado para outra versão (init_db.py grava a versão em DbVersion)."""
        try:
            row = await self.server_repository.db.fetch_one("SELECT Phase FROM DbVersion")
        except Exception:
            row = None  # banco antigo, sem DbVersion
        if row is None:
            print(f"[db] banco sem versão; rode `python init_db.py {name}`")
        elif row['Phase'] != name:
            print(f"[db] AVISO: o banco é {row['Phase']} e este servidor é {name} (patentes e seeds de outra versão)")

    async def stop(self):
        helper = getattr(self, '_ggauth50_helper', None)
        if helper is not None:
            await helper.close()
        self.task.cancel()
        for t in self.tasks:
            t.cancel()
        try:
            await self.clients.close()
            await self.task
        except CancelledError:
            pass

        await self.server_repository.delete_all_users(self.config['host'], self.config['port'])

        await self.server_repository.insert_service_status(
            self.config['product_version'],
            int.from_bytes(socket.inet_aton(self.config['host']), 'little'),
            self.config['port'],
            'T'
        )

    async def tcp_listener(self):
        server = await asyncio.start_server(
            self.handler,
            self.config['host'],
            self.config['port']
        )
        print(f'GameServer iniciado em {self.config["host"]}:{self.config["port"]} (features={self.features:04X})')

        async with server:
            await server.serve_forever()

    def calc_features(self, config) -> int:
        features: int = 0
        for feature in config['features']:
            features |= feature
        return features
    