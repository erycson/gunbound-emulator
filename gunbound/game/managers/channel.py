from gunbound.game.channel import Channel

class ChannelManager:
    """
    @todo Verificar limites de usuários por canal.
    """
    _instance = None
    
    def __init__(self):
        self.channels: list[Channel] = [Channel(self, i) for i in range(8)]

    @classmethod
    def initialize(cls):
        if cls._instance is not None:
            raise RuntimeError("ChannelManager já inicializado!")

        cls._instance = cls()
        return cls._instance

    @classmethod
    def get(cls):
        if cls._instance is None:
            raise RuntimeError("ChannelManager não inicializado!")
        return cls._instance
    
    def get(self, id: int) -> Channel:
        return self.channels[id]
    
    def get_least_populated(self) -> Channel:
        return min(self.channels, key=lambda c: c.size())