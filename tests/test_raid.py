"""Raid debug deployment, menu selection and end-to-end mission outcomes."""

import random
import unittest
from unittest.mock import patch

from mechgame.runner import Game
from mechgame.ui.menu import DisplaySettings, start_menu


class RaidTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, scenario="raid_military_base",
                          rng=random.Random(7)).create_match()
        self.objective = self.match.raidObjective
        self.player, self.enemy = self.match.teamList

    def test_test_match_menu_selects_raid_and_skirmish_resets_selection(self):
        settings = DisplaySettings()
        with patch("builtins.input", return_value="t"), patch("builtins.print"):
            self.assertEqual(start_menu(settings).scenario, "raid_military_base")
        with patch("builtins.input", return_value="s"), patch("builtins.print"):
            self.assertEqual(start_menu(settings).scenario, "skirmish")

    def test_rosters_positions_and_enemy_orders(self):
        self.assertEqual([len(s.mechList) for s in self.player.squadsList], [5, 3])
        self.assertEqual([len(s.mechList) for s in self.enemy.squadsList], [3, 3, 3])
        for squad in self.enemy.squadsList:
            self.assertEqual(sum(m.mechClass.name == "Bastion" for m in squad.mechList), 2)
            self.assertEqual(sum(m.mechClass.name == "Kestrel" for m in squad.mechList), 1)
            self.assertEqual(squad.currentGoal.kind, "defend_location")
        self.assertEqual(len({tuple(e.pos) for e in self.match.entities}), 17)
        self.assertTrue(all(m.pos[0] <= 8 for s in self.player.squadsList for m in s.mechList))
        self.assertTrue(self.enemy.mapVisibility.show_all_terrain)

    def test_initial_deployment_cannot_be_seen_or_detected_by_overdrive(self):
        for squad in self.enemy.squadsList:
            for guard in squad.mechList:
                guard.radarOn = True
                guard.sensorBoostMultiplier = 1.4
                guard.visPower = int(guard.mechClass.visPower * 1.4)
                guard.getVisuals(self.match)
                self.assertFalse(guard.directlyVisibleEnemies)
                self.assertFalse(guard.trackedEnemies)

    def test_base_hold_requires_next_turn_then_extraction(self):
        squad = self.player.squadsList[0]
        mech = squad.squadLead
        mech.pos = list(next(iter(self.objective.base_tiles)))
        self.match.pov = mech
        self.match.nextSquadTurn()
        self.assertFalse(self.objective.raided)
        for _ in range(4):
            self.match.nextSquadTurn()
        self.assertTrue(self.objective.raided)
        self.assertFalse(self.match.matchOver)
        for member in self.player.squadsList:
            for entity in list(member.mechList):
                entity.pos = [0, 10]
                entity.flee(self.match)
        self.assertTrue(self.match._finish_if_decided())
        self.assertIs(self.match.winner, self.player)

    def test_leaving_the_base_interrupts_the_hold(self):
        squad = self.player.squadsList[0]
        mech = squad.squadLead
        mech.pos = list(next(iter(self.objective.base_tiles)))
        self.objective.end_turn(self.match, squad)
        mech.pos = [10, 10]
        self.objective.moved(mech)
        mech.pos = list(next(iter(self.objective.base_tiles)))
        self.objective.begin_turn(self.match, squad)
        self.assertFalse(self.objective.raided)

    def test_clearing_enemy_ends_match_even_if_raid_was_not_completed(self):
        for squad in self.enemy.squadsList:
            for mech in list(squad.mechList):
                mech.destroy(self.match)
        self.assertTrue(self.match._finish_if_decided())
        self.assertFalse(self.objective.raided)
        self.assertIn("FAILED", self.match.resultMessage)

    def test_early_extraction_fails(self):
        for squad in self.player.squadsList:
            for mech in list(squad.mechList):
                mech.pos = [0, 10]
                mech.flee(self.match)
        self.assertTrue(self.match._finish_if_decided())
        self.assertIs(self.match.winner, self.enemy)


if __name__ == "__main__":
    unittest.main()
