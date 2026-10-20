"""
Job diário de patentes (TotalGrade/SeasonGrade/CountryGrade e ranks), com a regra de cada versão. Cada servidor roda uma
versão só, então o banco guarda a patente na numeração dessa versão (docs/Níveis.md):
- 'th' (TH e S1): RankCalc do BatchGIS.exe de 2004 (0x4011f0, veio no pacote "Season 2 server"). Escala -4..19, admin 20.
- 'v584' (S2: v548 e v584): escada de 47 ícones do cliente. Escala 1..41, admin 0.
Para levar um banco de uma versão para a seguinte: init_db.py (TH -> WCS1 -> WCS2).
"""
import asyncio
from datetime import datetime, timedelta
from typing import NamedTuple

TOP_SCORE = 6900
# Abaixo de 6900 GP: faixa fixa (GP mínimo, grade) da tabela 0x4283b4 do BatchGIS
GP_GRADES = [(6000, 9), (5100, 10), (4200, 11), (3500, 12), (2800, 13), (2300, 14), (1800, 15), (1500, 16), (1200, 17), (1100, 18)]
# >= 6900 GP: pela posição. L[i] = int(C * p[i]) + 21, C = quantos têm >= 6900 (floats em 0x428390)
PCT = [0.001, 0.01, 0.03, 0.06, 0.10, 0.20, 0.30, 0.50, 0.70]
DRAGONS = [(1, -4), (5, -3), (21, -2)]  # pos <= L[0]: 1 / 2-5 / 6-21, depois -1
GM_GRADE = 20

# v584 (Level Up BR, 2010): o cliente desenha o u16 recebido direto como quadro do rank1/rank2.img de 47 ícones
# (0x435f60/0x436140; maior = melhor; >= 30 liga o rankeff30..39): 0 admin, 1 pintinho, 2..17 martelos e machados,
# 18..22 estrelas, 23..26 cetros, 27..29 dragões, 30..32 cavaleiros, 33..35 fênix, 36..38 medalhas, 39..41 coroas,
# 42 VIP, 43..45 troféus, 46 WC. GP mínimo de cada um: tabelas da Softnyx/Level Up Brasil (2010-2012, docs/Níveis.md).
# Medalhas e coroas pedem também a posição (top 100/50/10, 3/2/1), como as mesmas tabelas trazem. 42..46 nunca saem.
V584_LADDER = (
    (2000000, 41), (1000000, 40), (800000, 39), (600000, 38), (500000, 37), (400000, 36),
    (250000, 35), (200000, 34), (150000, 33), (104000, 32), (84000, 31), (64000, 30),
    (54000, 29), (44000, 28), (34000, 27), (29000, 26), (24000, 25), (19000, 24), (17000, 23),
    (15000, 22), (13000, 21), (12000, 20), (11000, 19), (10000, 18),
    (8800, 17), (7900, 16), (7000, 15), (6200, 14), (5400, 13), (4700, 12), (4000, 11), (3500, 10),
    (3000, 9), (2600, 8), (2200, 7), (1900, 6), (1600, 5), (1400, 4), (1200, 3), (1100, 2),
)
V584_TOP = {36: 100, 37: 50, 38: 10, 39: 3, 40: 2, 41: 1}  # medalha bronze/prata/ouro, coroa bronze/prata/ouro
V584_ADMIN, V584_CHICK = 0, 1


def positions(scores: list[int], grade_of) -> list[tuple[int, int]]:
    """scores ordenados desc -> (posição, grade). Empate repete a posição e a grade do primeiro do empate (1, 2, 2, 4)."""
    out, last = [], None
    for i, s in enumerate(scores):
        if out and s == last:
            out.append(out[-1])
            continue
        pos, last = i + 1, s
        out.append((pos, grade_of(s, pos)))
    return out


def grades(scores: list[int]) -> list[tuple[int, int]]:
    """Regra do TH/S1 (BatchGIS)."""
    count = sum(s >= TOP_SCORE for s in scores)
    limits = [int(count * p) + 21 for p in PCT]

    def grade_of(s, pos):
        if s < TOP_SCORE:
            return next((g for gp, g in GP_GRADES if s >= gp), 19)
        if pos > limits[0]:
            return max(g for g in range(9) if pos > limits[g])
        return next((g for n, g in DRAGONS if pos <= n), -1)
    return positions(scores, grade_of)


def v584_grade(score, rank=None) -> int:
    """Patente do S2 pelo GP (e pela posição, para medalhas e coroas)."""
    score, rank = int(score or 0), int(rank or 0)
    return next((g for gp, g in V584_LADDER
                 if score >= gp and (g not in V584_TOP or 0 < rank <= V584_TOP[g])), V584_CHICK)


def grades_v584(scores: list[int]) -> list[tuple[int, int]]:
    """Regra do S2 (v548/v584)."""
    return positions(scores, v584_grade)


class Rule(NamedTuple):
    grades: object   # scores desc -> [(posição, grade)]
    gm: int          # grade de admin: fica fora do ranking


RULES = {'th': Rule(grades, GM_GRADE), 'v584': Rule(grades_v584, V584_ADMIN)}


async def recalc(db, rule: str = 'th'):
    fn, gm = RULES[rule]
    for score, grade, rank in (('TotalScore', 'TotalGrade', 'TotalRank'), ('SeasonScore', 'SeasonGrade', 'SeasonRank')):
        rows = await db.fetch_all(f"SELECT Id, {score} AS s FROM Game WHERE {grade} <> {gm} AND NoRankUpdate = 0 "
                                  f"ORDER BY {score} DESC")
        for r, (pos, g) in zip(rows, fn([int(r['s'] or 0) for r in rows])):
            await db.execute(f"UPDATE Game SET {grade}=:g, {rank}=:r WHERE Id=:id", {'g': g, 'r': pos, 'id': r['Id']})
        if grade == "TotalGrade":  # servidor de um país só: nível de país = nível total
            await db.execute(f"UPDATE Game SET CountryGrade=TotalGrade, CountryRank=TotalRank WHERE TotalGrade <> {gm}")


async def migrate_th_to_v584(db) -> int:
    """S1 -> S2: admin 20 -> 0; os outros pelo GP e pela posição que já estão no banco (inclusive NoRankUpdate).
    Não é idempotente: rodar de novo trataria o admin 0 como jogador comum."""
    rows = await db.fetch_all("SELECT Id, TotalGrade, TotalScore, TotalRank, SeasonScore, SeasonRank FROM Game")
    for r in rows:
        if int(r['TotalGrade'] or 0) == GM_GRADE:
            total = season = V584_ADMIN
        else:
            total, season = v584_grade(r['TotalScore'], r['TotalRank']), v584_grade(r['SeasonScore'], r['SeasonRank'])
        await db.execute("UPDATE Game SET TotalGrade=:t, SeasonGrade=:s, CountryGrade=:t WHERE Id=:id",
                         {'t': total, 's': season, 'id': r['Id']})
    return len(rows)


async def daily(db, rule: str = 'th', hour: int = 4):
    while True:
        try:
            await recalc(db, rule)
        except Exception as e:
            print(f"[ranking] erro: {e}")
        now = datetime.now()
        nxt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        await asyncio.sleep(((nxt if nxt > now else nxt + timedelta(days=1)) - now).total_seconds())

# amostra do gamesnapshot original: 13000 -> -4, 11174 -> -3, 1124 -> 18, ~1000 -> 19
assert grades([13000, 11174, 6000, 1124, 1000]) == [(1, -4), (2, -3), (3, 9), (4, 18), (5, 19)]
assert [v584_grade(s) for s in (0, 1100, 1399, 1400, 8800, 10000, 54000, 2000000)] == [1, 2, 3, 4, 17, 18, 29, 35]
assert [v584_grade(2000000, rank=r) for r in (1, 2, 3, 10, 50, 100, 101)] == [41, 40, 39, 38, 37, 36, 35]
assert v584_grade(450000, rank=5) == 36
assert grades_v584([2000000, 2000000, 1000]) == [(1, 41), (1, 41), (3, 1)]
