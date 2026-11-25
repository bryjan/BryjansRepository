"""Raid debug deployment, menu selection and end-to-end mission outcomes."""

import random
import unittest
from unittest.mock import patch

from mechgame.runner import Game
from mechgame.ui.menu import DisplaySettings, start_menu
from mechgame.raid import ensure_land_access


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

    def test_deployments_vary_but_repeat_with_the_same_seed(self):
        positions = {tuple(self.match.pov.pos)}
        bases = {self.objective.base_tiles}
        for seed in (0, 1):
            match = Game(scenario="raid_military_base", rng=random.Random(seed)).create_match()
            positions.add(tuple(match.pov.pos))
            bases.add(match.raidObjective.base_tiles)
            self.assertFalse(any(route.kind == "raid_access" for route in match.mapFeatures.roads))
        self.assertEqual(len(positions), 3)
        self.assertEqual(len(bases), 3)
        repeat = Game(scenario="raid_military_base", rng=random.Random(7)).create_match()
        self.assertEqual(tuple(repeat.pov.pos), tuple(self.match.pov.pos))
        self.assertEqual(repeat.raidObjective.base_tiles, self.objective.base_tiles)

    def test_water_only_crossings_preserve_natural_land_approaches(self):
        for row in self.match.map[1:-1]:
            for cell in row[1:-1]:
                cell.terrain = self.match.plains
        self.match.mapFeatures.roads.clear()
        ensure_land_access(self.match, (5, 20), [(30, 20)])
        self.assertEqual(self.match.mapFeatures.roads, [])
        for y in range(1, self.match.mapHeight - 1):
            self.match.map[y][20].terrain = self.match.water
        ensure_land_access(self.match, (5, 20), [(30, 20)])
        crossings = [route for route in self.match.mapFeatures.roads if route.kind == "raid_bridge"]
        self.assertEqual(len(crossings), 1)
        self.assertEqual(len(crossings[0].tiles), 1)
        self.assertTrue(all(self.match.map[y][x].terrain is self.match.road for x, y in crossings[0].tiles))
        self.assertIs(self.match.map[20][5].terrain, self.match.plains)

    def test_rosters_positions_and_enemy_orders(self):
        self.assertEqual([len(s.mechList) for s in self.player.squadsList], [5, 3])
        self.assertEqual([len(s.mechList) for s in self.enemy.squadsList], [3, 2, 4])
        expected = [
            ["Kestrel", "Bastion", "Bastion"],
            ["Kestrel", "Lancer Type.M Mortar"],
            ["Lancer Type.A", "Lancer Type.A", "Lancer Type.A", "Lancer Type.S Pathfinder"],
        ]
        for squad, names in zip(self.enemy.squadsList, expected):
            self.assertEqual([m.mechClass.name for m in squad.mechList], names)
            self.assertEqual(squad.currentGoal.kind, "defend_location")
        self.assertEqual(len({tuple(e.pos) for e in self.match.entities}), 17)
        self.assertTrue(all(min(m.pos[0], m.pos[1], self.match.mapWidth - 1 - m.pos[0],
                                self.match.mapHeight - 1 - m.pos[1]) <= 12
                            for s in self.player.squadsList for m in s.mechList))
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
