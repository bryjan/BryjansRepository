import unittest
from types import SimpleNamespace
from unittest.mock import patch

import inputs
import printView
from mechgame.runner import Game


class InputTests(unittest.TestCase):
    def test_radar_toggle_changes_the_mech_state(self):
        match = SimpleNamespace(pov=SimpleNamespace(radarOn=False))

        with patch("builtins.print"):
            inputs.radarToggle(match)
            inputs.radarToggle(match)

        self.assertFalse(match.pov.radarOn)

    def test_receive_input_trims_and_normalizes_commands(self):
        match = SimpleNamespace(pov=SimpleNamespace(radarOn=False))

        with patch("builtins.input", return_value="  RADAR  "), patch("builtins.print"):
            inputs.receive_input(match)

        self.assertTrue(match.pov.radarOn)

    def test_n_switches_to_the_next_mech_in_the_squad(self):
        match = Game(map_size=20, window_size=9).create_match()
        active_mech = match.pov

        with patch("builtins.input", return_value="n"), patch("builtins.print"):
            inputs.receive_input(match)

        self.assertIsNot(match.pov, active_mech)

    def test_options_can_change_tactical_width_and_height_independently(self):
        match = Game(map_size=20, window_size=9).create_match()

        with patch("builtins.input", side_effect=["w", "15"]), patch("builtins.print"):
            inputs.optionsMenu(match)
        with patch("builtins.input", side_effect=["h", "11"]), patch("builtins.print"):
            inputs.optionsMenu(match)

        self.assertEqual(match.windowWidth, 15)
        self.assertEqual(match.windowHeight, 11)

    def test_tactical_side_panel_summarizes_the_active_mech(self):
        match = Game(map_size=20, window_size=9).create_match()

        lines = printView._side_panel_lines(match, height=9)

        self.assertEqual(len(lines), 9)
        self.assertTrue(all(len(line) == printView.SIDE_PANEL_WIDTH + 2 for line in lines))
        panel = "\n".join(lines)
        self.assertIn("B — Lancer Type.S Pathfinder", panel)
        self.assertIn("Abilities: Dash 2/2", panel)

    def test_target_summary_shows_distance_and_visual_hit_chance(self):
        match = Game(map_size=20, window_size=9).create_match()
        shooter = match.pov
        target = match.teamList[1].squadsList[0].mechList[0]
        shooter.pos = [2, 10]
        target.pos = [10, 10]
        shooter.directlyVisibleEnemies = [target]
        weapon = shooter.mechClass.gunList[0]

        with patch("builtins.print") as print_mock:
            inputs.printTargetingSummary(match, weapon, target)

        output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("distance 8.0 tiles", output)
        self.assertIn("Hit chance:", output)

    def test_target_summary_shows_hit_chance_for_highest_radar_id(self):
        match = Game(map_size=20, window_size=9).create_match()
        shooter = match.pov
        target = match.teamList[1].squadsList[0].mechList[0]
        shooter.pos = [2, 10]
        target.pos = [10, 10]
        shooter.directlyVisibleEnemies = []
        shooter.team.radarContacts[target] = {
            "level": 3,
            "radar_power": 1_000,
            "position": [10, 10],
            "speed": 0,
            "turn_start_pos": [10, 10],
        }

        with patch("builtins.print") as print_mock:
            inputs.printTargetingSummary(match, shooter.mechClass.gunList[0], target)

        output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("Hit chance:", output)

    def test_abilities_command_activates_the_selected_hull_ability(self):
        match = Game(map_size=20, window_size=9).create_match()
        match.pov.pos = [4, 4]
        for index, entity in enumerate(match.entities):
            if entity is not match.pov:
                entity.pos = [10 + index, 15]

        with patch("builtins.input", side_effect=["ab", "1", "d"]), patch("builtins.print"):
            inputs.receive_input(match)

        self.assertEqual(match.pov.pos, [7, 4])
        self.assertEqual(match.pov.mechClass.hull.abilities[0].charges, 1)

    def test_launcher_target_selection_reopens_the_launcher_menu(self):
        match = Game(map_size=20, window_size=9).create_match()
        launcher_mech = match.teamList[0].squadsList[0].mechList[3]
        launcher = launcher_mech.mechClass.gunList[0]
        selected_target = match.teamList[1].squadsList[0].mechList[0]
        match.pov = launcher_mech
        original_menu = inputs.launcherFireMenu

        with patch("builtins.input", return_value="t"), patch(
            "inputs.chooseLauncherTrackedContact", return_value=selected_target
        ), patch("inputs.launcherFireMenu") as reopened_menu:
            original_menu(match, launcher)

        reopened_menu.assert_called_once_with(match, launcher, selected_target)

    def test_direct_fire_target_selection_reopens_the_full_target_menu(self):
        match = Game(map_size=20, window_size=9).create_match()
        default_target = match.teamList[1].squadsList[0].mechList[0]
        selected_target = match.teamList[1].squadsList[0].mechList[1]
        weapon = match.pov.mechClass.gunList[0]
        original_menu = inputs.chooseFireTarget

        with patch("builtins.input", return_value="t"), patch(
            "inputs.chooseTrackedContact", return_value=selected_target
        ), patch("inputs.chooseFireTarget") as reopened_menu:
            original_menu(match, default_target, weapon)

        reopened_menu.assert_called_once_with(match, selected_target, weapon)

    def test_weapon_selection_keeps_radar_selected_target(self):
        match = Game(map_size=20, window_size=9).create_match()
        bastion = match.teamList[1].squadsList[0].mechList[0]
        selected_target = match.pov
        match.pov = bastion
        original_menu = inputs.gunMenu

        with patch("builtins.input", return_value="1"), patch("inputs.fire") as fire_mock:
            original_menu(match, selected_target)

        fire_mock.assert_called_once_with(match, selected_target)

    def test_non_explosive_launcher_ammo_hides_damage_in_its_profile(self):
        match = Game(map_size=20, window_size=9).create_match()
        mortar = match.teamList[0].squadsList[0].mechList[3]
        launcher = mortar.mechClass.gunList[0]
        launcher.select_ammo(1)  # Smoke is the second catalogued mortar shell.

        with patch("builtins.print") as print_mock:
            inputs.printLauncherProfile(mortar, launcher, [10, 10])

        output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("Smoke", output)
        self.assertNotIn("damage", output)

    def test_help_lists_every_main_command_and_footer_prioritizes_abilities(self):
        match = SimpleNamespace(advTurn=True)
        with patch("builtins.print") as print_mock:
            inputs.helpCommand(match)
        help_output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        for command in ("'fire'", "'r'", "'p'", "'rd'", "'ab'", "'look'", "'st'", "'sq'", "'rep'", "'o'", "'n'", "'end'", "'?'"):
            self.assertIn(command, help_output)
        self.assertFalse(match.advTurn)

        with patch("builtins.print") as print_mock:
            printView._print_tactical_footer(80)
        footer_output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("'ab' Abilities", footer_output)
        self.assertIn("'n' Next", footer_output)
        self.assertNotIn("'st' status", footer_output)
        self.assertNotIn("'o' Options", footer_output)
