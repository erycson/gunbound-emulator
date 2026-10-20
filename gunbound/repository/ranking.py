"""Recalcula TotalGrade/SeasonGrade e ranks como o job diário do servidor original (SQL portável)."""
import asyncio
from datetime import datetime, timedelta

# Abaixo de 6900 GP: faixa fixa (GP mínimo, grade)
GP_GRADES = [(6000, 9), (5100, 10), (4200, 11), (3500, 12), (2800, 13), (2300, 14), (1800, 15), (1500, 16), (1200, 17), (1100, 18)]
# >= 6900 GP: percentil acumulado entre esses jogadores, após os dragões (top 1 / 4 / 16)
# shortcut: percentis aproximados da tabela oficial, ajustar se achar os valores exatos
PCT_GRADES = [(0.01, -1), (0.03, 0), (0.06, 1), (0.10, 2), (0.15, 3), (0.22, 4), (0.30, 5), (0.40, 6), (0.55, 7), (1.0, 8)]
DRAGONS = [(1, -4), (5, -3), (21, -2)]
GM_GRADE = 20

def grades(scores: list[int]) -> list[int]:
    """scores ordenados desc -> grade de cada um."""
    top = [s for s in scores if s >= 6900]
    out = []
    for i, s in enumerate(scores):
        if s < 6900:
            out.append(next((g for gp, g in GP_GRADES if s >= gp), 19))
        else:
            d = next((g for n, g in DRAGONS if i < n), None)
            out.append(d if d is not None else next(g for p, g in PCT_GRADES if (i + 1) / len(top) <= p))
    return out

async def recalc(db):
    for score, grade, rank in (('TotalScore', 'TotalGrade', 'TotalRank'), ('SeasonScore', 'SeasonGrade', 'SeasonRank')):
        rows = await db.fetch_all(f"SELECT Id, {score} AS s FROM Game WHERE {grade} <> {GM_GRADE} ORDER BY {score} DESC")
        for i, (r, g) in enumerate(zip(rows, grades([int(r['s'] or 0) for r in rows]))):
            await db.execute(f"UPDATE Game SET {grade}=:g, {rank}=:r WHERE Id=:id", {'g': g, 'r': i + 1, 'id': r['Id']})
        if grade == "TotalGrade":  # servidor de um país só: nível de país = nível total
            await db.execute("UPDATE Game SET CountryGrade=TotalGrade, CountryRank=TotalRank WHERE TotalGrade <> 20")

async def daily(db, hour: int = 4):
    while True:
        try:
            await recalc(db)
        except Exception as e:
            print(f"[ranking] erro: {e}")
        now = datetime.now()
        nxt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        await asyncio.sleep(((nxt if nxt > now else nxt + timedelta(days=1)) - now).total_seconds())

assert grades([9000, 1000, 1150, 6000]) == [-4, 19, 18, 9]
