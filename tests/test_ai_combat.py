"""Coverage for the first visibility-limited AI combat pass."""

import math
import random
import unittest

from mechgame.ai import (
    execute_squad_combat, execute_squad_flee, execute_squad_movement,
    request_reinforcement,
)
from mechgame.runner import Game
from mechgame.teams import Squad


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

    def test_high_reserve_mech_spends_remaining_ap_on_direct_fire(self):
        """Healthy ammunition and energy reserves permit sustained fire."""
        squad = self.enemy_squad
        shooter = squad.squadLead
        squad.mechList = [shooter]
        shooter.squad = squad
        shooter.pos = [10, 10]
        shooter.directlyVisibleEnemies = [self.target]
        shooter.trackedEnemies = [self.target]
        for limb in self.target.mechClass.limbList:
            limb.hp = limb.startingHP = 1_000
        chain_gun = next(
            weapon for weapon in shooter.mechClass.gunList
            if weapon.name == "Sustained ChainGun"
        )
        starting_charges = chain_gun.charges

        execute_squad_combat(self.match, squad)

        self.assertLessEqual(chain_gun.charges, starting_charges - 2)

    def test_double_time_and_retreat_suppress_ai_fire(self):
        self.enemy_squad.setMovementPolicy(mode="double_time")
        starting_ap = [mech.ap for mech in self.enemy_squad.mechList]

        self.assertEqual(execute_squad_combat(self.match, self.enemy_squad), [])
        self.assertEqual([mech.ap for mech in self.enemy_squad.mechList], starting_ap)

        self.enemy_squad.setMovementPolicy(mode="move")
        self.enemy_squad.setCombatPosture("retreat")
        self.assertEqual(execute_squad_combat(self.match, self.enemy_squad), [])
        self.assertEqual([mech.ap for mech in self.enemy_squad.mechList], starting_ap)

    def test_retreating_squad_calls_in_range_smoke_support(self):
        """A squad in contact asks a separate artillery squad to screen it."""
        retreating_squad = self.player_squad
        retreating_squad.playerControlled = False
        mortar = next(
            mech for mech in retreating_squad.mechList
            if any(weapon.isLauncher for weapon in mech.mechClass.gunList)
        )
        retreating_squad.mechList.remove(mortar)
        support_squad = Squad("Support", [mortar], "Artillery")
        self.match.teamList[0].squadsList.append(support_squad)
        support_squad.team = self.match.teamList[0]
        retreating_squad.squadLead.pos = [15, 10]
        mortar.pos = [10, 10]
        retreating_squad.squadLead.noteCombat("enemy in visual range")
        retreating_squad.setCombatPosture("retreat")

        self.assertEqual(execute_squad_combat(self.match, retreating_squad), [])
        self.assertEqual(support_squad.smokeCallPosition, (15, 10))
        self.assertEqual(support_squad.smokeCallTurns, 1)

        execute_squad_combat(self.match, support_squad)

        launcher = next(weapon for weapon in mortar.mechClass.gunList if weapon.isLauncher)
        self.assertEqual(launcher.selected_ammo.payload, "smoke")
        self.assertTrue(self.match.pendingImpacts)

    def test_flee_order_moves_an_ai_mech_to_the_border_and_preserves_it(self):
        """An ordered withdrawal exits intact rather than ejecting or dying."""
        squad = self.enemy_squad
        mech = squad.squadLead
        squad.mechList = [mech]
        mech.squad = squad
        mech.pos = [1, 10]
        for entity in self.match.entities:
            if entity is not mech:
                entity.pos = [20, 20]
        squad.orderFlee()

        moved = execute_squad_flee(self.match, squad)

        self.assertIn(mech, moved)
        self.assertTrue(mech.fled)
        self.assertTrue(mech.pilot.returned)
        self.assertEqual(mech.pilot.status, "RTB")
        self.assertIn(mech, self.match.fledMechs)
        self.assertNotIn(mech, self.match.destroyedMechs)
        self.assertNotIn(mech, self.match.entities)

    def test_spent_artillery_without_team_supplies_marks_itself_for_fleeing(self):
        mortar = next(
            mech for mech in self.player_squad.mechList
            if "artillery" in mech.mechClass.roles
        )
        for weapon in mortar.mechClass.gunList:
            for ammo in weapon.ammoTypes:
                ammo.charges = 0
        self.match.teamList[0].supplies = 0

        mortar.refreshReadiness(self.match)

        self.assertFalse(mortar.hasAvailableRole)
        self.assertTrue(mortar.shouldFlee)

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

    def test_melee_mech_closes_when_its_lance_beats_sidearm_dps(self):
        """A stronger short-range weapon preserves AP to close before firing."""
        squad = self.player_squad
        squad.playerControlled = False
        mech = next(
            entity for entity in squad.mechList
            if any(weapon.isMelee for weapon in entity.mechClass.gunList)
        )
        squad.mechList = [mech]
        squad.squadLead = mech
        mech.squad = squad
        target = self.enemy_squad.squadLead
        mech.pos = [10, 10]
        target.pos = [13, 10]
        mech.directlyVisibleEnemies = [target]
        mech.trackedEnemies = [target]
        for entity in self.match.entities:
            if entity not in {mech, target}:
                entity.pos = [30, 30]
        starting_ap = mech.ap

        execute_squad_combat(self.match, squad)

        self.assertIs(mech.approachTarget, target)
        self.assertEqual(mech.ap, starting_ap)
        execute_squad_movement(self.match, squad)
        lance = next(weapon for weapon in mech.mechClass.gunList if weapon.isMelee)
        self.assertLessEqual(math.dist(mech.pos, target.pos), lance.maxRange)

    def test_artillery_launches_after_an_unclear_two_turn_review(self):
        squad = self.player_squad
        squad.playerControlled = False
        mortar = next(
            mech for mech in squad.mechList
            if any(weapon.isLauncher for weapon in mech.mechClass.gunList)
        )
        support = next(
            mech for mech in squad.mechList if "anti_heavy" in mech.mechClass.roles
        )
        squad.mechList = [support, mortar]
        squad.squadLead = support
        support.squad = squad
        mortar.squad = squad
        squad.refreshCombatForce()
        support.pos = [9, 10]
        mortar.pos = [10, 10]
        for index, friendly in enumerate(self.match.entities):
            if friendly not in {support, mortar}:
                friendly.pos = [2, 2 + index]
        self.target = self.enemy_squad.squadLead
        self.target.pos = [15, 10]
        mortar.directlyVisibleEnemies = [self.target]
        mortar.trackedEnemies = [self.target]
        support.noteCombat("enemy in visual range")
        mortar.noteCombat("enemy in visual range")

        execute_squad_combat(self.match, squad)
        self.assertEqual(self.match.pendingImpacts, [])
        execute_squad_combat(self.match, squad)
        self.assertTrue(self.match.pendingImpacts)

    def test_overwhelming_observed_force_orders_contact_avoidance(self):
        squad = self.player_squad
        squad.playerControlled = False
        squad.squadLead.pos = [10, 10]
        # This test isolates force assessment from the new sustained-fire
        # behavior; damaged weapons leave the observed enemy force intact.
        for mech in squad.mechList:
            for weapon in mech.mechClass.gunList:
                weapon.hp = 0
        for index, enemy in enumerate(self.enemy_squad.mechList):
            enemy.pos = [14 + index, 10]
        squad.squadLead.directlyVisibleEnemies = list(self.enemy_squad.mechList)
        squad.squadLead.trackedEnemies = list(self.enemy_squad.mechList)
        squad.squadLead.noteCombat("enemy in visual range")

        execute_squad_combat(self.match, squad)
        execute_squad_combat(self.match, squad)

        self.assertTrue(squad.avoidContact)
        self.assertIsNotNone(squad.avoidanceTarget)

    def test_anti_heavies_share_a_near_matching_combat_target(self):
        squad = self.player_squad
        squad.playerControlled = False
        anti_heavies = [
            mech for mech in squad.mechList if "anti_heavy" in mech.mechClass.roles
        ]
        target = next(mech for mech in self.enemy_squad.mechList if mech.size == 3)
        target.pos = [14, 10]
        for index, mech in enumerate(anti_heavies):
            mech.pos = [10 - index * 3, 10]
            mech.directlyVisibleEnemies = [target]
            mech.trackedEnemies = [target]

        execute_squad_combat(self.match, squad)

        self.assertTrue(anti_heavies)
        self.assertTrue(all(squad.assignedTargets.get(mech) is target for mech in anti_heavies))

    def test_anti_swarm_mech_opportunistically_prioritizes_a_damaged_target(self):
        swarm_mech = next(
            mech for mech in self.enemy_squad.mechList if "anti_swarm" in mech.mechClass.roles
        )
        close_target = self.player_squad.mechList[1]
        damaged_target = self.player_squad.mechList[2]
        swarm_mech.pos = [10, 10]
        close_target.pos = [11, 10]
        damaged_target.pos = [14, 10]
        close_target.mechClass.condition = 100
        damaged_target.mechClass.condition = 20
        swarm_mech.directlyVisibleEnemies = [close_target, damaged_target]
        swarm_mech.trackedEnemies = [close_target, damaged_target]

        execute_squad_combat(self.match, self.enemy_squad)

        self.assertIs(self.enemy_squad.assignedTargets[swarm_mech], damaged_target)

    def test_leader_waits_two_combat_turns_before_damage_assessment(self):
        squad = self.enemy_squad
        leader = squad.squadLead
        # Keep the observed contact outside all direct weapon ranges. The
        # test supplies damage figures directly and should not resolve fire.
        self.target.pos = [39, 10]
        leader.noteCombat("enemy in visual range")
        leader.directlyVisibleEnemies = [self.target]
        leader.trackedEnemies = [self.target]
        squad.damageGiven = 20
        squad.damageReceived = 5

        execute_squad_combat(self.match, squad)
        self.assertEqual(squad.engagementAssessment, "unassessed")
        self.assertEqual(squad.combatTurns, 1)

        execute_squad_combat(self.match, squad)

        self.assertEqual(squad.engagementAssessment, "favorable")
        self.assertGreater(squad.estimatedDamageGiven, squad.estimatedDamageReceived)
        self.assertIs(squad.primaryTarget, self.target)

    def test_player_squad_receives_a_critical_reinforcement_request(self):
        request_reinforcement(self.match, self.enemy_squad, self.player_squad)

        self.assertIs(self.player_squad.reinforcementRequest, self.enemy_squad)
        self.assertTrue(any(
            critical and "Reinforcement request" in message
            for message, critical, _ in self.player_squad.reportLog
        ))

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
