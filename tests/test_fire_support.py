"""Fire support continues through equal/losing combat, including withdrawal."""

import random
import unittest
from unittest.mock import patch

from mechgame import fire_support
from mechgame.ai import _fire_artillery_if_ordered, execute_squad_combat
from mechgame.catalog import create_mech
from mechgame.entities import Entity, Pilot
from mechgame.runner import Game
from mechgame.teams import Squad, Team


class FireSupportTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, rng=random.Random(0)).create_match()
        def squad(name, blueprint, position):
            mech = Entity(create_mech(blueprint), Pilot(name))
            mech.pos = list(position)
            return Squad(name, [mech], "combat")
        self.caller = squad("Caller", "lancer.type_a", (10, 10))
        self.artillery = squad("Mortars", "lancer.mortar", (10, 35))
        enemy = squad("Enemy", "lancer.type_a", (20, 10))
        team = Team("Friendly", [self.caller, self.artillery])
        self.match.teamList = [team, Team("Enemy", [enemy])]
        self.match.entities = [self.caller.squadLead, self.artillery.squadLead, enemy.squadLead]
        self.match.pov = self.caller.squadLead
        self.target = enemy.squadLead
        self.caller.squadLead.directlyVisibleEnemies = [self.target]
        self.caller.squadLead.inCombat = True
        self.caller.engagementAssessment = "unclear"
        self.weapon = next(weapon for weapon in self.artillery.squadLead.mechClass.gunList if weapon.isLauncher)
        for ammo in self.weapon.ammoTypes:
            ammo.charges = 3 if ammo.payload == "explosive" else 0
        self.he = next(ammo for ammo in self.weapon.ammoTypes if ammo.payload == "explosive")
        for row in self.match.map[1:-1]:
            for cell in row[1:-1]:
                cell.terrain = self.match.plains

    def test_equal_and_losing_calls_keep_firing_below_half_ammo(self):
        for turn, assessment in enumerate(("unclear", "unfavorable", "unfavorable")):
            self.match.matchRound = turn
            self.caller.engagementAssessment = assessment
            self.artillery.squadLead.ap = 6
            fire_support.update(self.match, self.caller)
            self.assertIs(self.artillery.artilleryCallTarget, self.target)
            with patch("builtins.print"):
                self.assertTrue(_fire_artillery_if_ordered(self.match, self.artillery, self.artillery.squadLead))
            fire_support.clear_shot(self.artillery)
        self.assertEqual(self.he.charges, 0)
        self.assertEqual(len(self.match.pendingImpacts), 3)
        fire_support.update(self.match, self.caller)
        self.assertIsNone(self.artillery.artilleryCallTarget)

    def test_retreating_caller_still_requests_fire_support(self):
        self.caller.setCombatPosture("retreat")
        self.caller.engagementAssessment = "unfavorable"
        self.caller.avoidContact = True
        self.caller.avoidanceTarget = (3, 10)
        with patch("builtins.print"):
            execute_squad_combat(self.match, self.caller)
        self.assertIs(self.artillery.artilleryCallTarget, self.target)
        self.assertTrue(self.caller.avoidContact)
        self.assertEqual(self.caller.avoidanceTarget, (3, 10))

    def test_favorable_or_ended_combat_cancels_outstanding_call(self):
        for end_combat in (False, True):
            self.caller.engagementAssessment = "unclear"
            self.caller.squadLead.inCombat = True
            fire_support.update(self.match, self.caller)
            if end_combat:
                self.caller.squadLead.inCombat = False
            else:
                self.caller.engagementAssessment = "favorable"
            fire_support.update(self.match, self.caller)
            self.assertIsNone(self.artillery.artilleryCallTarget)
            self.assertEqual(self.artillery.artilleryCallTurns, 0)
            self.assertTrue(self.artillery.supportRequests[0].dismissed)

    def test_lost_contact_uses_reported_position_instead_of_hidden_motion(self):
        fire_support.update(self.match, self.caller)
        self.caller.squadLead.directlyVisibleEnemies = []
        self.target.pos = [35, 35]
        self.caller.engagementAssessment = "unfavorable"
        self.match.matchRound += 1
        fire_support.update(self.match, self.caller)
        self.assertEqual(self.artillery.artilleryCallPosition, (20, 10))
        with patch.object(self.weapon, "launchAt", return_value=True) as launch:
            self.assertTrue(_fire_artillery_if_ordered(self.match, self.artillery, self.artillery.squadLead))
        self.assertEqual(launch.call_args.args[1], [20, 10])

    def test_manual_recipient_gets_one_warning_for_an_ongoing_call(self):
        self.artillery.playerControlled = self.artillery.playerCommandable = True
        for turn in range(3):
            self.match.matchRound = turn
            fire_support.update(self.match, self.caller)
        self.assertEqual(len(self.artillery.supportRequests), 1)
        self.assertEqual(sum(critical and "Artillery request" in message
                             for message, critical, _ in self.artillery.reportLog), 1)


if __name__ == "__main__":
    unittest.main()
