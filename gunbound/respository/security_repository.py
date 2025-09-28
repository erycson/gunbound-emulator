
from gunbound.base.managers import DatabaseManager

class SecurityRepository:
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

    async def insert_current_user(self, user_id: str, context: int, server_ip: int, server_port: int) -> None:
        """Insert user into current users."""
        await self.db.execute(
            "INSERT INTO CurrentUser SET Id = :user_id, Context = :context, ServerIP = :server_ip, ServerPort = :server_port, LoggingTime = NOW()",
            {'user_id': user_id, 'context': context, 'server_ip': server_ip, 'server_port': server_port}
        )

    async def insert_login_log(self, user_id: str, server_ip: int, server_port: int, client_ip: int, client_port: int, block_ip: int, block_port: int) -> None:
        """Insert login log entry."""
        await self.db.execute(
            "INSERT DELAYED INTO LoginLog (Id, Ip, Ip_v, Port, Port_v, Time, ServerIp, ServerPort) "
            "VALUES (:user_id, :client_ip, :block_ip, :client_port, :block_port, NOW(), :server_ip, :server_port)",
            {'user_id': user_id, 'client_ip': client_ip, 'block_ip': block_ip, 'client_port': client_port, 'block_port': block_port, 'server_ip': server_ip, 'server_port': server_port}
        )