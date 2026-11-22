"""Coverage for the first visibility-limited AI combat pass."""

import random
import unittest

from mechgame.ai import execute_squad_combat, execute_squad_movement
from mechgame.runner import Game


class AiCombatTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        for row in self.match.map:
            for cell in row:
                cell.terrain = self.match.plains
        self.enemy_squad = self.match.teamList[1].squadsList[0]
        self.player_squad = self.match.teamList[0].squadsList[0]
        self.target = self.player_squad.squadLead
        self.target.pos = [12, 10]
        for index, mech in enumerate(self.enemy_squad.mechList):
            mech.pos = [10 - index * 3, 10]
            mech.directlyVisibleEnemies = [self.target]
            mech.trackedEnemies = [self.target]

    def test_ai_fires_at_a_visual_enemy_with_a_direct_weapon(self):
        starting_ap = [mech.ap for mech in self.enemy_squad.mechList]
        player_pov = self.match.pov

        fired = execute_squad_combat(self.match, self.enemy_squad)

        self.assertTrue(fired)
        self.assertTrue(any(mech.ap < ap for mech, ap in zip(self.enemy_squad.mechList, starting_ap)))
        self.assertTrue(all(mech.inCombat for mech in fired))
        self.assertIs(self.match.pov, player_pov)

    def test_double_time_and_retreat_suppress_ai_fire(self):
        self.enemy_squad.setMovementPolicy(mode="double_time")
        starting_ap = [mech.ap for mech in self.enemy_squad.mechList]

        self.assertEqual(execute_squad_combat(self.match, self.enemy_squad), [])
        self.assertEqual([mech.ap for mech in self.enemy_squad.mechList], starting_ap)

        self.enemy_squad.setMovementPolicy(mode="move")
        self.enemy_squad.setCombatPosture("retreat")
        self.assertEqual(execute_squad_combat(self.match, self.enemy_squad), [])
        self.assertEqual([mech.ap for mech in self.enemy_squad.mechList], starting_ap)

    def test_low_ammo_mech_needs_attack_order_to_fire_on_radar_contact(self):
        shooter = self.enemy_squad.mechList[-1]
        shooter.directlyVisibleEnemies = []
        shooter.trackedEnemies = [self.target]
        for weapon in shooter.mechClass.gunList:
            if not weapon.isLauncher and not weapon.isMelee:
                weapon.charges = 1
        self.match.issueTeamObjective(
            self.match.teamList[1], "defend", 80, (10, 10), "Hold position.",
        )
        original_ap = shooter.ap

        execute_squad_combat(self.match, self.enemy_squad)
        self.assertEqual(shooter.ap, original_ap)

        self.enemy_squad.setCombatPosture("attack")
        execute_squad_combat(self.match, self.enemy_squad)
        self.assertLess(shooter.ap, original_ap)

    def test_melee_weapon_is_used_against_a_close_visual_target(self):
        shooter = self.enemy_squad.mechList[-1]
        shooter.pos = [10, 10]
        self.target.pos = [11, 10]
        shooter.directlyVisibleEnemies = [self.target]
        shooter.trackedEnemies = [self.target]
        for weapon in shooter.mechClass.gunList:
            if not weapon.isMelee and not weapon.isLauncher and weapon.charges is not None:
                weapon.charges = 0
        starting_ap = shooter.ap

        fired = execute_squad_combat(self.match, self.enemy_squad)

        self.assertIn(shooter, fired)
        self.assertEqual(shooter.lastFiredAt, self.target.pos)
        self.assertLess(shooter.ap, starting_ap)

    def test_artillery_only_launches_under_an_attack_order(self):
        squad = self.player_squad
        squad.playerControlled = False
        mortar = next(
            mech for mech in squad.mechList
            if any(weapon.isLauncher for weapon in mech.mechClass.gunList)
        )
        mortar.pos = [10, 10]
        self.target = self.enemy_squad.squadLead
        self.target.pos = [15, 10]
        mortar.directlyVisibleEnemies = [self.target]
        mortar.trackedEnemies = [self.target]

        execute_squad_combat(self.match, squad)
        self.assertEqual(self.match.pendingImpacts, [])

        squad.setCombatPosture("attack")
        execute_squad_combat(self.match, squad)
        self.assertTrue(self.match.pendingImpacts)

    def test_attack_order_marks_a_low_accuracy_contact_for_approach(self):
        target = self.target
        target.pos = [35, 10]
        for index, mech in enumerate(self.enemy_squad.mechList):
            mech.pos = [5 - index * 3, 10]
            mech.directlyVisibleEnemies = []
            mech.trackedEnemies = [target]
        self.enemy_squad.setCombatPosture("attack")
        leader = self.enemy_squad.squadLead

        execute_squad_combat(self.match, self.enemy_squad)

        self.assertIs(self.enemy_squad.primaryTarget, target)
        execute_squad_movement(self.match, self.enemy_squad)
        self.assertGreater(leader.pos[0], 5)


if __name__ == "__main__":
    unittest.main()
