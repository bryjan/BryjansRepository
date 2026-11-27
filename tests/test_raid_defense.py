"""Shared visual base alarms override patrols while preserving attack orders."""

import random
import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mechgame.ai import SquadGoal, _leader_destination, execute_squad_combat, execute_squad_movement
from mechgame.raid import BASE_DEFENSE_PRIORITY, BASE_DEFENSE_RADIUS
from mechgame.runner import Game


class RaidDefenseTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(scenario="raid_military_base", rng=random.Random(1)).create_match()
        self.raid = self.match.raidObjective
        self.player, self.defender = self.match.teamList
        self.attacker = self.player.squadsList[0].squadLead

    def see_base_attacker(self):
        self.attacker.pos = list(next(iter(self.raid.base_tiles)))
        self.defender.sharedVisibleTiles.add(tuple(self.attacker.pos))

    def test_alarm_recalls_every_squad_and_persists_without_contact(self):
        self.see_base_attacker()
        self.raid.update_defense(self.match, self.defender)
        self.assertTrue(self.raid.defense_alert)
        self.assertEqual(self.defender.currentGoal.kind, "return_to_defend")
        for squad in self.defender.squadsList:
            self.assertEqual(squad.currentGoal.kind, "return_to_defend")
            self.assertEqual(squad.currentGoal.priority, BASE_DEFENSE_PRIORITY)
            self.assertFalse(squad.patrolRoute)
            self.assertEqual(squad.movementMode, "move")
            self.assertIn(tuple(_leader_destination(self.match, squad)), self.raid.base_tiles)
        histories = [len(s.goalHistory) for s in self.defender.squadsList]
        self.defender.sharedVisibleTiles.clear()
        self.attacker.pos = [5, 5]
        self.match.matchRound += 1
        self.raid.update_defense(self.match, self.defender)
        self.assertEqual([len(s.goalHistory) for s in self.defender.squadsList], histories)
        self.assertEqual(len(self.defender.reportLog), 1)

    def test_hidden_and_radar_only_nearby_attackers_do_not_raise_alarm(self):
        self.attacker.pos = list(next(iter(self.raid.base_tiles)))
        self.defender.radarContacts[self.attacker] = {"position": tuple(self.attacker.pos), "level": 3}
        for squad in self.defender.squadsList:
            for mech in squad.mechList:
                mech.trackedEnemies = [self.attacker]
        self.raid.update_defense(self.match, self.defender)
        self.assertFalse(self.raid.defense_alert)
        self.assertEqual(self.defender.squadsList[1].currentGoal.kind, "patrol_location")

    def test_visible_but_distant_attacker_does_not_raise_alarm(self):
        self.attacker.pos = [5, 5]
        self.assertGreater(min(math.dist(self.attacker.pos, point)
                               for point in self.raid.base_tiles), BASE_DEFENSE_RADIUS)
        self.defender.sharedVisibleTiles.add(tuple(self.attacker.pos))
        self.raid.update_defense(self.match, self.defender)
        self.assertFalse(self.raid.defense_alert)

    def test_attack_order_stays_first_with_recall_queued_above_patrol(self):
        squad = self.defender.squadsList[1]
        patrol = squad.currentGoal
        attack = SquadGoal("attack_test", "attack_test", "attack", 100,
                           ((10, 10),), "Attack first.")
        squad.currentGoal = attack
        squad.currentGoals = [attack, patrol]
        self.see_base_attacker()
        self.raid.update_defense(self.match, self.defender)
        self.assertIs(squad.currentGoal, attack)
        self.assertEqual(_leader_destination(self.match, squad), (10, 10))
        self.assertEqual([goal.kind for goal in squad.currentGoals],
                         ["attack", "return_to_defend", "patrol_location"])
        squad.currentGoals.remove(attack)
        self.raid.update_defense(self.match, self.defender)
        self.assertEqual(squad.currentGoal.kind, "return_to_defend")
        self.assertFalse(squad.patrolRoute)

    def test_movement_entry_point_triggers_recall_without_combining_enemy_intel(self):
        self.see_base_attacker()
        squad = self.defender.squadsList[1]
        with patch("builtins.print"):
            execute_squad_movement(self.match, squad)
        self.assertEqual(squad.currentGoal.kind, "return_to_defend")
        self.assertEqual(self.defender.squadsList[2].currentGoal.kind, "return_to_defend")
        self.assertFalse(self.attacker.trackedEnemies)

    def test_combat_entry_point_sends_team_recall(self):
        self.see_base_attacker()
        with patch("builtins.print"):
            execute_squad_combat(self.match, self.defender.squadsList[0])
        self.assertTrue(all(s.currentGoal.kind == "return_to_defend" for s in self.defender.squadsList))

    def test_combined_attack_keeps_its_destination_ahead_of_recall(self):
        squad = self.defender.squadsList[1]
        order = SimpleNamespace(state="attacking", target_positions={self.attacker: (10, 10)})
        squad.combinedAttack = order
        self.see_base_attacker()
        self.raid.update_defense(self.match, self.defender)
        self.assertIs(squad.combinedAttack, order)
        self.assertEqual(_leader_destination(self.match, squad), (10, 10))


if __name__ == "__main__":
    unittest.main()
