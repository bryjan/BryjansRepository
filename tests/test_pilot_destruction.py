import random
import unittest

from mechgame.runner import Game


class PilotDestructionTests(unittest.TestCase):
    def test_hull_energy_capacity_uses_its_energy_stat(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()

        self.assertEqual(match.pov.mechClass.energyMax, 20)

    def test_destroyed_cockpit_removes_mech_from_active_match(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()
        mech = match.pov

        mech.cockpit.damage(match)
        self.assertEqual(mech.cockpit.status, 1)
        self.assertIn(mech, match.entities)
        self.assertTrue(any("Cockpit hit" in report[0] for report in mech.squad.reportLog))

        mech.cockpit.damage(match)
        self.assertEqual(mech.cockpit.status, 0)
        self.assertNotIn(mech, match.entities)
        self.assertNotIn(mech, mech.squad.mechList)
        self.assertIn(mech, match.destroyedMechs)
