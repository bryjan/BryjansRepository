"""Regression coverage for visibility-limited combat-state signals."""

import random
import unittest

from mechgame.runner import Game


class CombatAwarenessTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        for row in self.match.map:
            for cell in row:
                cell.terrain = self.match.plains
        self.player = self.match.teamList[0].squadsList[0]
        self.enemy = self.match.teamList[1].squadsList[0]

    def test_visual_contact_marks_the_mech_and_its_squad_in_combat(self):
        observer = self.player.squadLead
        target = self.enemy.squadLead
        observer.pos = [10, 10]
        target.pos = [11, 10]

        observer.getVis(self.match)

        self.assertTrue(observer.inCombat)
        self.assertEqual(observer.lastCombatSignal, "enemy in visual range")
        self.assertTrue(self.player.inCombat)

    def test_direct_fire_marks_combat_but_artillery_fire_does_not(self):
        direct_shooter = self.player.squadLead
        self.match.pov = direct_shooter
        direct_shooter.pos = [10, 10]
        direct_weapon = next(
            weapon for weapon in direct_shooter.mechClass.gunList if not weapon.isLauncher
        )

        direct_weapon.shootAt(self.match, [12, 10])

        self.assertTrue(direct_shooter.inCombat)
        artillery_shooter = next(
            mech for mech in self.player.mechList
            if any(weapon.isLauncher for weapon in mech.mechClass.gunList)
        )
        artillery_shooter.pos = [15, 10]
        self.match.pov = artillery_shooter
        artillery_weapon = next(
            weapon for weapon in artillery_shooter.mechClass.gunList if weapon.isLauncher
        )

        artillery_weapon.launchAt(self.match, [20, 10])

        self.assertFalse(artillery_shooter.inCombat)

    def test_taking_damage_and_seeing_an_explosion_mark_combat(self):
        victim = self.player.squadLead
        victim.pos = [10, 10]
        victim.mechClass.hull.damage(self.match, 100, "test", armorPiercing=True)
        self.assertTrue(victim.inCombat)
        self.assertEqual(victim.lastCombatSignal, "took damage")

        observer = self.player.mechList[1]
        observer.pos = [5, 5]
        impact_cell = self.match.map[10][10]
        observer.visibleCells = [impact_cell]
        self.match.explosion([10, 10], radius=0, size=0, damage=0)

        self.assertTrue(observer.inCombat)
        self.assertEqual(observer.lastCombatSignal, "saw an explosion")

    def test_combat_memory_expires_after_two_quiet_personal_turns(self):
        mech = self.player.squadLead
        mech.pos = [5, 5]
        for enemy in self.enemy.mechList:
            enemy.pos = [35, 35]
        mech.noteCombat("fired a direct weapon")

        mech.roundRefresh(self.match)
        self.assertTrue(mech.inCombat)
        self.assertEqual(mech.combatQuietTurns, 1)
        mech.roundRefresh(self.match)

        self.assertFalse(mech.inCombat)
        self.assertEqual(mech.combatQuietTurns, 0)


if __name__ == "__main__":
    unittest.main()
