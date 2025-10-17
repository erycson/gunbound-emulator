from gunbound.game.channel import Channel

class ChannelManager:
    """
    @todo Verificar limites de usuários por canal.
    """
    def __init__(self):
        self.channels: list[Channel] = [Channel(self, i) for i in range(8)]

    def get(self, id: int) -> Channel:
        return self.channels[id]

    def get_least_populated(self) -> Channel:
        return min(self.channels, key=lambda c: c.size())