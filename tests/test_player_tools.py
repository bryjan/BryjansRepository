"""Friendly delegation, manual orders, travel interruption and battle totals."""

import random
import unittest
from unittest.mock import patch

from mechgame.runner import Game
from mechgame import after_action, squad_orders, travel
from mechgame.commands.orders import control_menu, order_menu


class PlayerToolsTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(4)).create_match()
        self.squad = self.match.playerSquad
        self.leader = self.squad.squadLead
        self.enemy = self.match.teamList[1].squadsList[0].squadLead

    def test_control_can_be_returned_to_manual_and_rejects_enemy(self):
        squad_orders.set_control(self.squad, ai=True)
        self.assertFalse(self.squad.playerControlled)
        self.assertTrue(self.squad.playerCommandable)
        squad_orders.set_control(self.squad, ai=False)
        self.assertTrue(self.squad.playerControlled)
        with self.assertRaises(ValueError):
            squad_orders.set_control(self.enemy.squad, ai=False)

    def test_control_and_orders_are_accessible_from_menus(self):
        with patch("builtins.input", side_effect=["1", "a"]), patch("mechgame.commands.orders.pv.printPOV"):
            control_menu(self.match)
        self.assertFalse(self.squad.playerControlled)
        with patch("builtins.input", side_effect=["1", "m", "15,12"]), patch("mechgame.commands.orders.pv.printPOV"):
            order_menu(self.match)
        self.assertEqual(self.squad.currentGoal.locations, ((15, 12),))
        self.assertTrue(self.squad.manualOrder)

    def test_attack_rejects_unknown_target_and_flee_is_executable(self):
        with self.assertRaises(ValueError):
            squad_orders.issue(self.match, self.squad, "attack", target=self.enemy)
        squad_orders.issue(self.match, self.squad, "flee")
        self.assertTrue(self.squad.fleeOrdered)
        self.assertEqual(self.squad.movementMode, "double_time")

    def test_automatic_travel_uses_resources_and_stops_on_arrival(self):
        for row in self.match.map:
            for cell in row:
                cell.terrain = self.match.plains
        self.squad.mechList = [self.leader]
        self.match.entities = [self.leader, self.enemy]
        self.leader.pos = [10, 10]
        self.enemy.pos = [35, 35]
        self.squad.autoTravelTarget = (14, 10)
        energy, ap = self.leader.energy, self.leader.ap
        travel.advance(self.match, self.squad)
        self.assertEqual(self.leader.pos, [14, 10])
        self.assertIsNone(self.squad.autoTravelTarget)
        self.assertLess(self.leader.energy, energy)
        self.assertEqual(self.leader.ap, ap - 4)

    def test_automatic_travel_pauses_for_contact_without_spending_ap(self):
        self.squad.autoTravelTarget = (15, 15)
        self.leader.trackedEnemies = [self.enemy]
        ap = self.leader.ap
        travel.advance(self.match, self.squad)
        self.assertIsNone(self.squad.autoTravelTarget)
        self.assertEqual(self.leader.ap, ap)

    def test_automatic_travel_yields_when_more_than_one_turn_is_needed(self):
        for row in self.match.map:
            for cell in row:
                cell.terrain = self.match.plains
        self.squad.mechList = [self.leader]
        self.match.entities = [self.leader, self.enemy]
        self.leader.pos = [5, 5]
        self.enemy.pos = [35, 35]
        self.squad.autoTravelTarget = (20, 5)
        travel.advance(self.match, self.squad)
        self.assertTrue(self.match.turnEnded)
        self.assertEqual(self.squad.autoTravelTarget, (20, 5))
        self.assertNotEqual(self.leader.pos, [20, 5])

    def test_after_action_uses_cumulative_totals_and_removed_units(self):
        self.match.recordCombatDamage(self.leader, self.enemy, 12)
        self.squad.damageGiven = 0
        self.enemy.destroy(self.match)
        self.match.resultMessage = "Test complete"
        report = "\n".join(after_action.summary(self.match))
        self.assertIn("Damage dealt: 12", report)
        self.assertIn("Mechs destroyed: 1", report)
        self.assertIn(self.enemy.pilot.display_name, report)

    def test_launcher_damage_is_credited_to_owning_team(self):
        self.match.recordCombatDamage(self.leader.team, self.enemy, 20)
        self.assertEqual(self.match.damageDealt[self.leader.team], 20)
        self.assertEqual(self.match.damageReceived[self.enemy.team], 20)

    def test_fire_damage_retains_team_credit(self):
        from mechgame.effects import FireEffect
        limb = self.enemy.mechClass.limbList[0]
        limb.armor = 0
        with patch.object(self.match.rng, "choice", return_value=limb), patch.object(limb, "critical"):
            FireEffect(owner_team=self.leader.team).on_enter(self.match, self.enemy)
        self.assertEqual(self.match.damageDealt[self.leader.team], 8)

    def test_after_action_counts_lost_pilots(self):
        self.enemy.pilot.kill(self.match)
        self.enemy.destroy(self.match)
        report = "\n".join(after_action.summary(self.match))
        self.assertIn("Pilots lost: 1", report)
        self.assertIn("Killed: " + self.enemy.pilot.display_name, report)

    def test_extraction_does_not_automatically_recover_evading_pilots(self):
        self.leader.eject(self.match)
        self.leader.pilot.status = "Evading"
        self.leader.pilot.returned = False
        for mech in list(self.squad.mechList):
            mech.pos = [0, 10]
            mech.flee(self.match)
        self.match.resolvePilotSurvival()
        self.assertEqual(self.leader.pilot.status, "Evading")
        self.assertIn("Pilots lost: 1", "\n".join(after_action.summary(self.match)))


if __name__ == "__main__":
    unittest.main()
