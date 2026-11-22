import random
import unittest

from mechgame.runner import Game


class PilotDestructionTests(unittest.TestCase):
    def test_hull_energy_capacity_uses_its_energy_stat(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()

        self.assertEqual(match.pov.mechClass.energyMax, 20)

    def test_destroyed_cockpit_removes_mech_from_active_match(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
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
        self.assertEqual(mech.pilot.status, "KIA")

    def test_in_combat_ejection_uses_the_base_survival_odds_without_nearby_mechs(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        mech = match.pov
        match.entities = [mech]
        match.map[mech.pos[1]][mech.pos[0]].terrain = match.plains
        mech.inCombat = True

        self.assertEqual(mech.ejectionOdds(match), {"RTB": 25, "Lost": 50, "Captured": 25})

    def test_lost_pilots_return_after_the_last_enemy_force_is_removed(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        pilot = match.pov.pilot
        pilot.status = "Lost"
        match.ejectedPilots.append(pilot)

        for enemy in list(match.teamList[1].squadsList[0].mechList):
            enemy.destroy(match)
        match.resolvePilotSurvival()

        self.assertEqual(pilot.status, "RTB")
        self.assertTrue(pilot.returned)
