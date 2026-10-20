from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING
from gunbound.util import synchronized
from gunbound.base.protocol import BasePackageSend
if TYPE_CHECKING:
    from gunbound.game.client import ClientConnection

class Channel:
    """
    @todo Verificar limites de usuários por canal.
    @todo Verificar limites de salas por canal.
    """
    def __init__(self, manager, id: int):
        self.id = id
        self.clients: dict[int, 'ClientConnection'] = {}
        self.slots: dict[int, int] = {}   # conn.id -> posição fixa no canal (menor vaga livre, até sair)
        self.lock = asyncio.Lock()

    @synchronized()
    async def add(self, client: 'ClientConnection') -> bool:
        if client.id in self.clients or len(self.clients) >= 255:
            return False
        used = set(self.slots.values())
        self.slots[client.id] = next(i for i in range(256) if i not in used)
        self.clients[client.id] = client
        return True

    @synchronized()
    async def remove(self, client: 'ClientConnection') -> bool:
        if client.id not in self.clients:
            return False
        del self.clients[client.id]
        del self.slots[client.id]
        return True

    @synchronized()
    async def get_all(self) -> list[tuple[int, 'ClientConnection']]:
        """(posição, conexão) ordenado pela posição. A posição não muda enquanto o jogador está no canal:
        o cliente identifica cada jogador por ela nos avisos de entrada (0x200E) e saída (0x200F)."""
        return sorted(((self.slots[cid], c) for cid, c in self.clients.items()), key=lambda t: t[0])

    async def broadcast(self, packet, onlys: None | list[int] = None, excepts: None | list[int] = None) -> None:
        """
        Envia um ou vários pacotes para todos os usuários conectados no canal de forma assíncrona e de alta performance, sem aguardar conclusão.
        packets pode ser um BasePackageSend único ou uma lista deles.
        Args:
            packet (BasePackageSend): O pacote a ser enviado.
            onlys (list[int] | None): Lista de IDs de clientes que devem receber o pacote. Se None, todos recebem.
            excepts (list[int] | None): Lista de IDs de clientes que não devem receber
            encrypted (bool): Se o pacote deve ser criptografado antes do envio usando a chave de criptografia do cliente.
        """
        clients = await self.get_all()
        for _, client in clients:
            if onlys and client.id not in onlys:
                continue
            if excepts and client.id in excepts:
                continue
            asyncio.create_task(client.on_send(packet.clone()))

    def size(self) -> int:
        return len(self.clients)

    def get_client_position(self, client: 'ClientConnection') -> int | None:
        return self.slots.get(client.id)

    def get_highest_channel_position(self) -> int:
        return max(self.slots.values(), default=0)
