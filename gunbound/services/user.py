from gunbound.respository.user_profile_repository import UserProfileRepository
from gunbound.respository.game_stats_repository import GameStatsRepository
from gunbound.respository.records_repository import RecordsRepository
from gunbound.respository.inventory_repository import InventoryRepository
from gunbound.respository.security_repository import SecurityRepository
from gunbound.respository.messaging_repository import MessagingRepository
from typing import Dict, Any, Optional
import asyncio

class UserService:
    def __init__(self):
        self.user_profile = UserProfileRepository()
        self.game_stats = GameStatsRepository()
        self.records = RecordsRepository()
        self.inventory = InventoryRepository()
        self.security = SecurityRepository()
        self.messaging = MessagingRepository()

    async def login_user(self, user_id: str, context: int, server_ip: int, server_port: int, client_ip: int, client_port: int) -> Optional[Dict[str, Any]]:
        """
        Orchestrate login: fetch data in parallel from all services, then insert logs.
        Returns a dict with all user data if successful, None if user not found.
        """
        try:
            # Parallel fetches from independent services
            user_profile, game_data, stage_records, mobile_records, is_blocked, chest_data, cash_data, money_data, gift_msgs = await asyncio.gather(
                self.user_profile.get_user_profile(user_id),
                self.game_stats.get_game_data(user_id),
                self.records.get_stage_records(user_id),
                self.records.get_mobile_records(user_id),
                self.security.is_blocked(client_ip),
                self.inventory.get_chest_data(user_id),
                self.inventory.get_cash_data(user_id),
                self.game_stats.get_money_data(user_id),
                self.messaging.get_gift_msgs(user_id)
            )

            if not user_profile:
                return None

            # Sequential inserts via security service
            await self.security.insert_current_user(user_id, context, server_ip, server_port)
            await self.security.insert_login_log(user_id, client_ip, client_port, server_ip, server_port)

            return {
                'user': user_profile,
                'game': game_data,
                'stage_records': stage_records,
                'mobile_records': mobile_records,
                'is_blocked': is_blocked,
                'chest': chest_data,
                'cash': cash_data,
                'money': money_data,
                'gifts': gift_msgs
            }
        except Exception as e:
            print(f"Error during login for user {user_id}: {e}")
            raise

    async def logout_user(self, user_id: str, context: int) -> bool:
        """
        Orchestrate logout via security service.
        """
        try:
            return await self.security.logout_user(user_id, context)
        except Exception as e:
            print(f"Error during logout for user {user_id}: {e}")
            return False
