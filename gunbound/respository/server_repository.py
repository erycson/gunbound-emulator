
from sqlite3 import IntegrityError
from gunbound.base.managers import DatabaseManager
from gunbound.broker.managers.gameserver import socket

class ServerRepository:
    def __init__(self):
        self.db = DatabaseManager.get()

    async def is_ip_blocked(self, client_ip) -> bool:
        """Check if IP is blocked. Returns True if blocked, False otherwise."""
        data = await self.db.fetch_one(
            "SELECT Allow FROM IpBlock WHERE (:ip & Mask) = Ip ORDER BY Mask DESC LIMIT 1",
            {'ip': client_ip}
        )
        print(client_ip, data)
        return True if data and data['Allow'] == 0 else False

    async def insert_current_user(self, user_id: str, context: int, server_ip: int, server_port: int) -> bool:
        """
        Insere um usuário na tabela CurrentUser.

        Achei essas outras consultas, mas não vi utilidade, e achei melhor usar o um INSERT com UNIQUE KEY em Id
        SELECT Context, ServerIP, ServerPort FROM CurrentUser WHERE Id='admin'
        REPLACE CurrentUser SET Id='admin', Context=724922815, ServerIP=26219180, ServerPort=8360, LoggingTime=NOW()

        Args:
            user_id (str): O identificador único do usuário.
            context (int): O identificador de contexto da sessão. Basicamente serve para saber o que o usuário está fazendo, podendo associar aos logs
            server_ip (int): O endereço IP do servidor. Em little-endian.
            server_port (int): A porta do servidor.

        Returns:
            bool: True se inserção bem-sucedida, False se o usuário já estiver logado.
        """
        await self.db.execute(
            "INSERT INTO CurrentUser SET Id = :user_id, Context = :context, ServerIP = :server_ip, ServerPort = :server_port, LoggingTime = NOW()",
            {'user_id': user_id, 'context': context, 'server_ip': server_ip, 'server_port': server_port}
        )
        return True
    
    async def delete_current_user(self, user_id: str) -> None:
        """
        Remove um usuário da tabela CurrentUser.
        No servidor original ele adiciona o Context, mas não vejo necessidade.

        Args:
            user_id (str): O identificador único do usuário.
        """
        await self.db.execute(
            "DELETE FROM CurrentUser WHERE Id = :user_id",
            {'user_id': user_id}
        )

    async def insert_login_log(self, user_id: str, server_ip: int, server_port: int, client_ip: int, client_port: int, block_ip: int, block_port: int) -> None:
        """
        Insere uma entrada de log de login.

        Args:
            user_id (str): O identificador único do usuário.
            server_ip (int): O endereço IP do servidor. Em little-endian.
            server_port (int): A porta do servidor.
            client_ip (int): O endereço IP do cliente obtido a partir do socket no servidor. Em little-endian.
            client_port (int): A porta do cliente obtido a partir do socket no servidor.
            block_ip (int): O endereço IP do cliente que ele enviou no bloco 3. Em little-endian.
            block_port (int): A porta do cliente que ele enviou no bloco 3.
        """
        await self.db.execute(
            "INSERT DELAYED INTO LoginLog (Id, Ip, Ip_v, Port, Port_v, Time, ServerIp, ServerPort) "
            "VALUES (:user_id, :client_ip, :block_ip, :client_port, :block_port, NOW(), :server_ip, :server_port)",
            {'user_id': user_id, 'client_ip': client_ip, 'block_ip': block_ip, 'client_port': client_port, 'block_port': block_port, 'server_ip': server_ip, 'server_port': server_port}
        )

    async def insert_service_status(self, product_version: int, server_ip: int, server_port: int, status: str) -> None:
        """
        Insere uma entrada de log de status do serviço.

        Args:
            product_version (int): A versão do produto.
            server_ip (int): O endereço IP do servidor. Em little-endian.
            server_port (int): A porta do servidor.
            status (str): O status do serviço. Deve ser 'T' (Terminated) para offline ou 'S' (Started) para online.
        """

        if status not in ('T', 'S'):
            raise ValueError("Status deve ser 'T' ou 'S'")

        await self.db.execute(
            "INSERT INTO ServiceStatus (SerialNo, Time, ServerIp, ServerPort, Status) VALUES (:product_version, NOW(), :server_ip, :server_port, :status)",
            {'product_version': product_version, 'server_ip': server_ip, 'server_port': server_port, 'status': status}
        )

    async def insert_user_count(self, product_version: int, server_ip: int, server_port: int, user_count: int) -> None:
        await self.db.execute(
            "INSERT INTO UserCount (SerialNo, ServerIp, ServerPort, Time, UserCount) VALUES (:product_version, :server_ip, :server_port, NOW(), :user_count)",
            {'product_version': product_version, 'server_ip': server_ip, 'server_port': server_port, 'user_count': user_count}
        )