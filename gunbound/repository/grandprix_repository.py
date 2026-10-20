from gunbound.base.database import Database


class GrandPrixRepository:
    """
    Tabelas GrandPrix_Personal / GrandPrix_Group do original. Group.ScoreOnCalc guarda a pontuação do grupo
    (o original faz "Score=Score+%d" numa coluna que o schema não tem).
    Ranking: SQL comum aos três bancos (sem window function nem UPDATE ... FROM): lê ordenado e grava a posição
    com executemany numa transação só.
    """

    def __init__(self, db: Database):
        self.db = db

    async def personal(self, user_id: str) -> dict | None:
        return await self.db.fetch_one(
            "SELECT Score, Rank, RankOld, Win, Lose, Category FROM GrandPrix_Personal WHERE User=:u", {'u': user_id})

    async def add_personal(self, user_id: str, score: int, win: bool) -> None:
        col = 'Win' if win else 'Lose'
        if not await self.db.execute(
                f"UPDATE GrandPrix_Personal SET Score=Score+:s, {col}={col}+1 WHERE User=:u", {'s': score, 'u': user_id}):
            await self.db.execute(
                "INSERT INTO GrandPrix_Personal (User, Score, Rank, RankOld, Win, Lose) VALUES (:u, :s, 0, 0, :w, :l)",
                {'u': user_id, 's': score, 'w': int(win), 'l': int(not win)})

    async def add_group(self, category: int, score: int, win: bool) -> None:
        col = 'Win' if win else 'Lose'
        await self.db.execute(
            f"UPDATE GrandPrix_Group SET ScoreOnCalc=ScoreOnCalc+:s, {col}={col}+1 WHERE Category=:c",
            {'s': score, 'c': str(category)})

    async def refresh_ranks(self) -> None:
        """RankOld = Rank; Rank = posição por pontuação (1 = melhor)."""
        transaction = await self.db.transaction()
        try:
            users = await self.db.fetch_all("SELECT User FROM GrandPrix_Personal ORDER BY Score DESC")
            if users:
                await self.db.execute("UPDATE GrandPrix_Personal SET RankOld=Rank, Rank=:r WHERE User=:u",
                                      [{'r': i, 'u': row['User']} for i, row in enumerate(users, 1)])
            groups = await self.db.fetch_all("SELECT Category, ScoreOnCalc FROM GrandPrix_Group")
            groups.sort(key=lambda g: int(g['ScoreOnCalc'] or 0), reverse=True)
            if groups:
                await self.db.execute("UPDATE GrandPrix_Group SET RankOld=Rank, Rank=:r WHERE Category=:c",
                                      [{'r': i, 'c': g['Category']} for i, g in enumerate(groups, 1)])
            await transaction.commit()
        except Exception:
            await transaction.rollback()
            raise

    async def rankers(self, limit: int) -> tuple[list[dict], list[dict]]:
        groups = await self.db.fetch_all(
            "SELECT Category, ScoreOnCalc, Rank, RankOld, Win, Lose FROM GrandPrix_Group WHERE Rank > 0 ORDER BY Rank")
        people = await self.db.fetch_all(
            "SELECT u.Nickname, g.Category, g.Score, g.Rank, g.RankOld, g.Win, g.Lose FROM GrandPrix_Personal AS g "
            "INNER JOIN User AS u ON g.User=u.Id WHERE g.Rank > 0 ORDER BY g.Rank LIMIT :n", {'n': limit})
        return groups, people
