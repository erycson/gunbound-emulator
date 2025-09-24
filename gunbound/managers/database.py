import databases

class DatabaseManager:
    _instance = None

    def __init__(self, uri):
        self._database = databases.Database(uri)

    @classmethod
    async def initialize(cls, uri):
        if cls._instance is not None:
            raise RuntimeError("DatabaseManager já inicializado!")

        try:
            self = cls(uri)
            await self._database.connect()
            cls._instance = self
        except Exception as e:
            import sys
            print(f"Erro ao conectar ao banco de dados: {e}", file=sys.stderr)
            sys.exit(1)

    @classmethod
    def get(cls):
        if cls._instance is None:
            raise RuntimeError("DatabaseManager não inicializado!")
        return cls._instance._database

    async def disconnect(self):
        await self._database.disconnect()
