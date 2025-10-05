from gunbound.base.managers import DatabaseManager
from typing import Dict, Any, List

class RecordsRepository:
    def __init__(self):
        self.db = DatabaseManager.get_instance()

    async def get_stage(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch stage win/lose records."""
        records = await self.db.fetch_all(
            "SELECT Stage, Win, Lose FROM StageRecord WHERE Id = :user_id",
            {'user_id': user_id}
        )
        return [dict(r) for r in records]

    async def get_mobile(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch mobile win/lose records."""
        records = await self.db.fetch_all(
            "SELECT Mobile, Win, Lose FROM MobileRecord WHERE Id = :user_id",
            {'user_id': user_id}
        )
        return [dict(r) for r in records]