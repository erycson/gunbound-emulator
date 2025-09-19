# lib/protocol/login.py

from gunbound.broker.protocol.enums import ClientPacket, ServerPacket
from gunbound.broker.protocol.base import BasePackageFactory, BasePackageRecv, BasePackageSend
from gunbound.broker.managers.config import ConfigManager
from gunbound.util.class_loader import instantiate_by_fullname

@BasePackageFactory.register(ClientPacket.CLI_LOGIN.value)
class LoginRecv(BasePackageRecv):
    _strategy = None

    def __init__(self, conn):
        self.conn = conn
        self.strategy = self.get_strategy()

    @classmethod
    def get_strategy(cls):
        if cls._strategy is None:
            config = ConfigManager.get()
            strategy_class = config['broker']['strategies']['login']
            cls._strategy = instantiate_by_fullname(strategy_class)
        return cls._strategy

    async def process(self, buf):
        # Delegar para a estratégia selecionada
        session_id, username, password = await self.strategy.process(self.conn, buf)
        print(f"[LoginRecv] Login processado: {username}/{password}")

class LoginResp(BasePackageSend):
    def __init__(self, payload):
        self.cmd = ServerPacket.LOGIN_RESPONSE.value
        self.payload = payload

    @classmethod
    def success(cls, user):
        return cls({'status': 'ok', 'user': user})

    @classmethod
    def userNotFound(cls, username):
        return cls({'status': 'not_found', 'username': username})

    def to_bytes(self):
        # Serialização para bytes (exemplo: JSON)
        import json
        return json.dumps(self.payload).encode()