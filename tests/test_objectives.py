"""Briefed markers respect fog and request details retain sensor snapshots."""

import random
import unittest
from unittest.mock import patch

from mechgame.runner import Game
from mechgame import objectives
from mechgame.ai import request_reinforcement
from mechgame.commands.objectives import objectiveMenu
from mechgame.ui import tactical


class ObjectiveTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(2)).create_match()
        self.squad = self.match.playerSquad
        self.sender = self.match.teamList[1].squadsList[0]

    def test_briefed_base_visible_without_discovering_terrain_or_enemies(self):
        cell = self.match.map[30][30]
        self.match.mapFeatures.add_objective("base", "Raid Military Base", "raid_military_base", [cell.pos])
        enemy = self.sender.squadLead
        enemy.pos = list(cell.pos)
        self.squad.team.exploredTiles.clear()
        self.squad.team.mapVisibility.show_all_objectives = True
        with patch("mechgame.ui.tactical.termcolor.colored", return_value="base") as color, patch("builtins.print") as output, patch.object(enemy, "displayObject") as enemy_symbol:
            tactical._display_overview_chunk(self.match, [[cell]])
        color.assert_called_once_with("M", "green")
        output.assert_called_once_with("base", end=" ")
        enemy_symbol.assert_not_called()
        self.assertNotIn((30, 30), self.squad.team.exploredTiles)
        self.squad.team.mapVisibility.show_all_objectives = False
        with patch("mechgame.ui.tactical.termcolor.colored", return_value="fog") as color, patch("builtins.print"):
            tactical._display_overview_chunk(self.match, [[cell]])
        color.assert_called_once_with("?", "dark_grey")

    def test_requests_are_deduplicated_addressed_and_expire(self):
        target = self.sender.squadLead
        request = objectives.request_support(self.match, self.sender, self.squad, "Artillery", (12, 13), "Fire support needed.", target)
        objectives.request_support(self.match, self.sender, self.squad, "Artillery", (14, 13), "Updated request.", target)
        self.assertEqual(len(self.squad.supportRequests), 1)
        target.pos = [35, 35]
        entry = next(item for item in objectives.items(self.match, self.squad) if item.request is request)
        self.assertIn("[14, 13]", " ".join(entry.details))
        self.assertNotIn("[35, 35]", " ".join(entry.details))
        self.assertFalse(any(item.request is request for item in objectives.items(self.match, self.sender)))
        self.match.matchRound += 3
        self.assertEqual(request.status(self.match), "Expired")

    def test_reinforcement_requests_enter_objective_menu(self):
        request_reinforcement(self.match, self.sender, self.squad)
        self.assertEqual(self.squad.supportRequests[0].kind, "Reinforcements")

    def test_menu_shows_and_dismisses_request_without_advancing_turn(self):
        request = objectives.request_support(self.match, self.sender, self.squad, "Smoke", (15, 15), "Cover retreat.")
        entries = objectives.items(self.match, self.squad)
        index = next(i for i, item in enumerate(entries, 1) if item.request is request)
        with patch("builtins.input", side_effect=[str(index), "d", "x"]), patch("mechgame.commands.objectives.pv.print_overview") as render:
            objectiveMenu(self.match)
        self.assertTrue(request.dismissed)
        self.assertFalse(self.match.turnEnded)
        self.assertTrue(any("OBJECTIVE DETAILS" in call.kwargs["right_panel"][0] for call in render.call_args_list))


if __name__ == "__main__":
    unittest.main()
