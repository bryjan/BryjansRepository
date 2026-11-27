"""Reinforcement calls supplement retreat and send one available ally to help."""

import random
import unittest
from unittest.mock import patch

from mechgame import reinforcements
from mechgame.ai import SquadGoal, _entity_combat_force, execute_squad_combat, execute_squad_movement
from mechgame.catalog import create_mech
from mechgame.entities import Entity, Pilot
from mechgame.runner import Game
from mechgame.teams import Squad, Team


class ReinforcementTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, rng=random.Random(0)).create_match()
        def make_squad(name, position):
            mech = Entity(create_mech("lancer.type_a"), Pilot(name))
            mech.pos = list(position)
            squad = Squad(name, [mech], "combat")
            squad.currentGoal = SquadGoal(name, name, "patrol_location", 100, ((30, 30),))
            squad.currentGoals = [squad.currentGoal]
            return squad
        self.caller = make_squad("Caller", (16, 10))
        self.helper = make_squad("Helper", (5, 10))
        self.reserve = make_squad("Reserve", (5, 30))
        self.enemy = make_squad("Enemy", (18, 10))
        team = Team("Friends", [self.caller, self.helper, self.reserve])
        enemy = Team("Enemy", [self.enemy])
        team.mapVisibility.show_all_terrain = True
        self.match.teamList = [team, enemy]
        self.match.entities = [s.squadLead for s in [self.caller, self.helper, self.reserve, self.enemy]]
        self.match.pov = self.caller.squadLead
        self.target = self.enemy.squadLead
        self.caller.squadLead.directlyVisibleEnemies = [self.target]
        self.caller.squadLead.inCombat = True
        for row in self.match.map[1:-1]:
            for cell in row[1:-1]:
                cell.terrain = self.match.plains

    def test_equal_force_calls_one_nearest_helper_and_ai_moves_toward_caller(self):
        helper = reinforcements.consider(self.match, self.caller, [self.target])
        self.assertIs(helper, self.helper)
        self.assertEqual(helper.currentGoal.kind, "reinforce")
        self.assertEqual(helper.currentGoal.locations, ((16, 10),))
        self.assertIsNone(self.reserve.reinforcementRequest)
        with patch("builtins.print"):
            self.assertTrue(execute_squad_movement(self.match, helper))
        self.assertGreater(helper.squadLead.pos[0], 5)

    def test_losing_call_keeps_retreat_calculations_intact(self):
        self.caller.combatForce = _entity_combat_force(self.target) * 3
        self.caller.engagementAssessment = "unfavorable"
        self.caller.avoidContact = True
        self.caller.avoidanceTarget = (3, 10)
        self.caller.setCombatPosture("retreat")
        with patch("builtins.print"):
            execute_squad_combat(self.match, self.caller)
        self.assertIs(self.helper.reinforcementRequest, self.caller)
        self.assertTrue(self.caller.avoidContact)
        self.assertEqual(self.caller.avoidanceTarget, (3, 10))
        self.assertEqual(self.caller.combatPosture, "retreat")

    def test_weaker_contact_does_not_call_for_help(self):
        self.caller.combatForce = _entity_combat_force(self.target) * 2
        self.assertIsNone(reinforcements.consider(self.match, self.caller, [self.target]))

    def test_repeated_calls_update_retreat_location_without_recruiting_more_squads(self):
        reinforcements.consider(self.match, self.caller, [self.target])
        self.caller.squadLead.pos = [13, 10]
        self.match.matchRound += 1
        reinforcements.consider(self.match, self.caller, [self.target])
        self.assertEqual(self.helper.currentGoal.locations, ((13, 10),))
        self.assertEqual(len(self.helper.supportRequests), 1)
        self.assertIsNone(self.reserve.reinforcementRequest)

    def test_manual_helper_receives_one_critical_request_without_moving(self):
        self.helper.playerControlled = self.helper.playerCommandable = True
        original = list(self.helper.squadLead.pos)
        with patch("builtins.print"):
            reinforcements.consider(self.match, self.caller, [self.target])
            reinforcements.consider(self.match, self.caller, [self.target])
        self.assertEqual(self.helper.squadLead.pos, original)
        self.assertEqual(self.helper.currentGoal.kind, "patrol_location")
        self.assertEqual(sum(critical and "Reinforcement request" in message
                             for message, critical, _ in self.helper.reportLog), 1)

    def test_expired_response_restores_standing_order(self):
        previous = self.helper.currentGoal
        reinforcements.consider(self.match, self.caller, [self.target])
        self.match.matchRound += 3
        reinforcements.prepare(self.match, self.helper)
        self.assertIsNone(self.helper.reinforcementRequest)
        self.assertIs(self.helper.currentGoal, previous)

    def test_busy_attackers_and_base_guard_are_not_requisitioned(self):
        self.helper.currentGoal = SquadGoal("guard", "guard", "defend_location", 100,
                                          ((5, 10),), objective_id="raid_base")
        self.helper.currentGoals = [self.helper.currentGoal]
        self.reserve.setCombatPosture("attack")
        self.assertIsNone(reinforcements.consider(self.match, self.caller, [self.target]))

    def test_combat_execution_requests_help_before_disengaging(self):
        with patch("builtins.print"):
            execute_squad_combat(self.match, self.caller)
        self.assertIs(self.helper.reinforcementRequest, self.caller)


if __name__ == "__main__":
    unittest.main()
