from random import random
from gunbound.game.client import ClientConnection

class ClientManager:
    _instance = None
    
    def __init__(self):
        self.clients: map[int, ClientConnection] = {}

    @classmethod
    def initialize(cls):
        if cls._instance is not None:
            raise RuntimeError("ClientManager já inicializado!")

        cls._instance = cls()
        return cls._instance

    @classmethod
    def get(cls):
        if cls._instance is None:
            raise RuntimeError("ClientManager não inicializado!")
        return cls._instance
    
    def size(self) -> int:
        return len(self.clients)
    
    def add(self, client: ClientConnection):
        client.id = self.generate_id()
        self.clients[client.id] = client

    def generate_id(self) -> int:
        id = 0
        while id == 0 or id in self.clients:
            id = random.randint(1, 4294967295)  # Gera int32 positivo (0 a 2^32-1)
        return id
