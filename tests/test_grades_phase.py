"""Patentes e tarefas por versão. Uso: python -m unittest tests.test_grades_phase -v"""
import asyncio
import unittest
from types import SimpleNamespace
from gunbound.game import phase
from gunbound.game.room import by_grade
from gunbound.game_server import TASKS
from gunbound.repository import ranking


class FakeDb:
    def __init__(self, rows):
        self.rows, self.updates = rows, []

    async def fetch_all(self, query, values=None):
        return self.rows

    async def execute(self, query, values=None):
        self.updates.append(values)
        return 1


def player(slot, grade, phase_name):
    conn = SimpleNamespace(data={'game': {'TotalGrade': grade}}, server=SimpleNamespace(config={'phase': phase_name}))
    return SimpleNamespace(slot=slot, conn=conn)


class GradesPhaseTest(unittest.TestCase):
    def test_rules_and_tasks(self):
        for name in ('TH', 'WCS1', 'WCS2'):
            p = phase.PHASES[name]
            self.assertTrue(set(p.tasks) <= set(TASKS), name)
            self.assertIn(p.rank_rule, ranking.RULES)
        self.assertEqual((phase.PHASES['WCS1'].rank_rule, phase.PHASES['WCS2'].rank_rule), ('th', 'v584'))
        self.assertEqual(ranking.RULES['v584'].gm, phase.PHASES['WCS2'].gm_grade)

    def test_by_grade_strongest_first(self):
        th = [player(0, 19, 'WCS1'), player(1, -4, 'WCS1'), player(2, 5, 'WCS1')]
        self.assertEqual([p.slot for p in by_grade(th)], [1, 2, 0])
        s2 = [player(0, 1, 'WCS2'), player(1, 41, 'WCS2'), player(2, 20, 'WCS2')]
        self.assertEqual([p.slot for p in by_grade(s2)], [1, 2, 0])

    def test_migrate_th_to_v584(self):
        db = FakeDb([
            {'Id': 'gm', 'TotalGrade': 20, 'TotalScore': 50000, 'TotalRank': 0, 'SeasonScore': 0, 'SeasonRank': 0},
            {'Id': 'a', 'TotalGrade': -4, 'TotalScore': 2000000, 'TotalRank': 1, 'SeasonScore': 1100, 'SeasonRank': 9},
            {'Id': 'b', 'TotalGrade': 19, 'TotalScore': 1000, 'TotalRank': 2, 'SeasonScore': 0, 'SeasonRank': 0},
        ])
        self.assertEqual(asyncio.run(ranking.migrate_th_to_v584(db)), 3)
        self.assertEqual([(u['t'], u['s']) for u in db.updates], [(0, 0), (41, 2), (1, 1)])

    def test_recalc_v584(self):
        db = FakeDb([{'Id': 'a', 's': 64000}, {'Id': 'b', 's': 1200}])
        asyncio.run(ranking.recalc(db, 'v584'))
        self.assertEqual(db.updates[:2], [{'g': 30, 'r': 1, 'id': 'a'}, {'g': 3, 'r': 2, 'id': 'b'}])


if __name__ == '__main__':
    unittest.main()
