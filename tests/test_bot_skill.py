"""Curva de acerto do bot e perfis de mobile. python -m unittest tests.test_bot_skill"""
import unittest
from gunbound.base.enums import HIDDEN_TANKS
from gunbound.bot import profiles, skill
from gunbound.bot.skill import ShotSituation as S
from gunbound.game import phase

DEFAULT = profiles.Shot()


class SkillTest(unittest.TestCase):
    def test_curve_from_floor_towards_ceil(self):
        self.assertAlmostEqual(skill.base(0), 0.25)
        self.assertLess(skill.base(1), 0.95)
        self.assertGreater(skill.base(1), 0.9)
        self.assertTrue(all(skill.base(a / 10) < skill.base((a + 1) / 10) for a in range(10)))

    def test_grade_scale_per_phase(self):
        self.assertEqual((skill.normalize('WCS1', 19), skill.normalize('WCS1', -4)), (0, 1))
        self.assertEqual((skill.normalize('WCS2', 1), skill.normalize('WCS2', 41), skill.normalize('WCS2', 0)), (0, 1, 1))
        self.assertEqual(skill.denormalize('WCS2', 0.5), 21)

    def test_ideal_shot_is_base_and_hard_shot_hurts_chick_more(self):
        ideal = S(angle=45, distance=0, max_distance=1000)
        self.assertAlmostEqual(skill.hit_chance(1, ideal, DEFAULT), skill.base(1))
        hard = S(angle=150, distance=900, max_distance=1000, wind=1, weather=True, wall=True)
        top, chick = skill.hit_chance(1, hard, DEFAULT), skill.hit_chance(0, hard, DEFAULT)
        self.assertGreater(top / skill.base(1), chick / skill.base(0))
        self.assertGreater(top, 0.3)
        self.assertLess(chick, 0.1)

    def test_angle(self):
        self.assertEqual(skill.angle_penalty(45, DEFAULT), 0)
        self.assertEqual(skill.angle_penalty(-20, DEFAULT), 0)  # para baixo: a distância cobra
        self.assertLess(skill.angle_penalty(90, DEFAULT), skill.angle_penalty(150, DEFAULT))
        self.assertAlmostEqual(skill.angle_penalty(195, DEFAULT), DEFAULT.max_pen)

    def test_boomer_vertical_and_mage_needs_space(self):
        boomer, mage = profiles.shot('WCS1', 0x05, 1), profiles.shot('WCS1', 0x01, 1)
        self.assertEqual(skill.angle_penalty(89, boomer), 0)
        self.assertGreater(skill.angle_penalty(89, DEFAULT), 0)
        close = S(angle=45, distance=50, max_distance=1000)
        self.assertIn('too_close', skill.penalties(close, mage))
        self.assertNotIn('too_close', skill.penalties(close, boomer))


class ProfilesTest(unittest.TestCase):
    def test_every_phase_tank_has_profile(self):
        for name, cls in (('TH', phase.TH), ('WCS1', phase.WCS1), ('WCS2', phase.WCS2)):
            missing = set(cls.tanks) - set(profiles.BY_PHASE[name])
            self.assertFalse(missing, f'{name}: {sorted(missing)}')
        self.assertIn(HIDDEN_TANKS[0], profiles.WCS1)

    def test_slot_10_and_14_change_between_th_and_wc(self):
        self.assertEqual((profiles.TH[0x0D].name, profiles.WCS1[0x0D].name), ('Dragon', 'Aduka'))
        self.assertEqual((profiles.TH[0x0E].name, profiles.WCS1[0x0E].name), ('Knight', 'Kalsiddon'))


if __name__ == '__main__':
    unittest.main()
