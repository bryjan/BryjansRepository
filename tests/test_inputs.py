import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mechgame.ui import tactical
from mechgame.commands import dispatch, firing, navigation, squad
from mechgame.runner import Game


class InputTests(unittest.TestCase):
    def test_radar_toggle_changes_the_mech_state(self):
        match = SimpleNamespace(pov=SimpleNamespace(radarOn=False))

        with patch("builtins.print"):
            navigation.radarToggle(match)
            navigation.radarToggle(match)

        self.assertFalse(match.pov.radarOn)

    def test_receive_input_trims_and_normalizes_commands(self):
        match = SimpleNamespace(pov=SimpleNamespace(radarOn=False))

        with patch("builtins.input", return_value="  RADAR  "), patch("builtins.print"):
            dispatch.receive_input(match)

        self.assertTrue(match.pov.radarOn)

    def test_quit_command_requests_a_return_to_the_start_menu(self):
        match = Game(map_size=20, window_size=9).create_match()

        with patch("builtins.input", return_value="quit"):
            dispatch.receive_input(match)

        self.assertTrue(match.quitRequested)
        self.assertFalse(match.matchOver)

    def test_weapon_menu_cancel_keeps_the_existing_default(self):
        match = Game(map_size=20, window_size=9).create_match()
        lancer = match.teamList[0].squadsList[0].mechList[1]
        chain_gun = next(weapon for weapon in lancer.mechClass.gunList if weapon.name == "ChainGun")
        chain_gun.defaultGun = True
        match.pov = lancer

        with patch("builtins.input", return_value="x"), patch("builtins.print"):
            firing.gunMenu(match)

        self.assertTrue(chain_gun.defaultGun)

    def test_look_can_cancel_without_rendering_a_view(self):
        match = Game(map_size=20, window_size=9).create_match()

        with patch("builtins.input", return_value="x"), patch("mechgame.ui.tactical.printPOV") as view_mock:
            navigation.lookAt(match)

        view_mock.assert_not_called()

    def test_m_opens_the_full_debug_map_without_ending_the_turn(self):
        match = Game(map_size=20, window_size=9).create_match()

        with patch("builtins.input", side_effect=["m", ""]), patch(
            "mechgame.ui.tactical.print_overview"
        ) as map_mock:
            dispatch.receive_input(match)

        map_mock.assert_called_once_with(match)
        self.assertFalse(match.advTurn)

    def test_overview_uses_weighted_votes_and_connected_route_bonus(self):
        match = Game(map_size=20, window_size=9).create_match()
        chunk = [row[2:6] for row in match.map[2:6]]
        for row in chunk:
            for cell in row:
                cell.terrain = match.plains

        chunk[0][0].terrain = match.urban
        self.assertIs(tactical.overview_terrain(chunk), match.plains)

        for cell in chunk[0]:
            cell.terrain = match.urban
        chunk[1][0].terrain = match.urban
        self.assertIs(tactical.overview_terrain(chunk), match.urban)

        for row in chunk:
            for cell in row:
                cell.terrain = match.plains
        for cell in chunk[1]:
            cell.terrain = match.road
        self.assertIs(tactical.overview_terrain(chunk), match.road)

        for row in chunk:
            for cell in row:
                cell.terrain = match.water
        for cell in chunk[1]:
            cell.terrain = match.road
        self.assertIs(tactical.overview_terrain(chunk), match.road)

    def test_n_switches_to_the_next_mech_in_the_squad(self):
        match = Game(map_size=20, window_size=9).create_match()
        active_mech = match.pov

        with patch("builtins.input", return_value="n"), patch("builtins.print"):
            dispatch.receive_input(match)

        self.assertIsNot(match.pov, active_mech)

    def test_options_can_change_tactical_width_and_height_independently(self):
        match = Game(map_size=20, window_size=9).create_match()

        with patch("builtins.input", side_effect=["w", "15"]), patch("builtins.print"):
            squad.optionsMenu(match)
        with patch("builtins.input", side_effect=["h", "19", "21"]), patch("builtins.print"):
            squad.optionsMenu(match)

        self.assertEqual(match.windowWidth, 15)
        self.assertEqual(match.windowHeight, 21)

    def test_options_choices_render_in_the_tactical_bottom_panel(self):
        match = Game(map_size=20, window_size=9).create_match()

        with patch("builtins.input", return_value="x"), patch(
            "mechgame.commands.squad.pv.printPOV",
        ) as panel:
            squad.optionsMenu(match)

        self.assertIn("'w' tactical width", panel.call_args.kwargs["command_text"])
        self.assertIn("'h' tactical height", panel.call_args.kwargs["command_text"])

    def test_tactical_side_panel_summarizes_the_active_mech(self):
        match = Game(map_size=20, window_size=9).create_match()
        match.pov.mechClass.legs.limbCon = 0.5
        match.pov.cockpit.status = 1

        lines = tactical._side_panel_lines(match, height=19)

        self.assertEqual(len(lines), 19)
        self.assertTrue(all(len(line) == tactical.SIDE_PANEL_WIDTH + 2 for line in lines))
        panel = "\n".join(lines)
        self.assertEqual(match.pov.mechClass.hull.asciiArt, (" /\\ ", "/##\\", " /\\ "))
        self.assertIn("B - Lancer Type.S Pathfinder", panel)
        self.assertIn("Most damaged: Pathfinder Lancer", panel)
        self.assertIn("Legs (50%)", panel)
        self.assertIn("Pilot: Injured (cockpit damaged)", panel)
        self.assertIn("Weapons:", panel)
        self.assertIn("Abilities: Dash 2/2", panel)

    def test_tactical_side_panel_defaults_to_nearest_tracked_contact(self):
        match = Game(map_size=20, window_size=9).create_match()
        observer = match.pov
        target = match.teamList[1].squadsList[0].mechList[0]
        observer.trackedEnemies = [target]
        observer.directlyVisibleEnemies = [target]

        panel = "\n".join(tactical._side_panel_lines(match, height=19))

        self.assertIn("FOCUS: Bastion", panel)
        self.assertIn("Sensors: Visual", panel)
        self.assertIn("Tracked contacts:", panel)

    def test_tactical_side_panel_warns_about_unread_critical_reports(self):
        match = Game(map_size=20, window_size=9).create_match()
        match.pov.squad.reportLog.append(["CRITICAL MESSAGE! Test", True, False])

        lines = tactical._side_panel_lines(match, height=19)

        self.assertIn("Critical reports!", lines[-1])

    def test_status_and_reports_use_tactical_panels(self):
        match = Game(map_size=20, window_size=9).create_match()
        match.pov.squad.reportLog.append(["Round: 1 | B: Test report", False, False])

        with patch("mechgame.ui.tactical.printPOV") as view_mock, patch("builtins.input", return_value="x"):
            navigation.statusPanel(match)
        self.assertNotIn("right_panel", view_mock.call_args.kwargs)

        with patch("mechgame.ui.tactical.printPOV") as view_mock, patch("builtins.input", return_value="x"):
            squad.unreadReportMenu(match)
        title, entries = view_mock.call_args.kwargs["right_panel"]
        self.assertEqual(title, "UNREAD REPORTS")
        self.assertIn("Test report", entries[0])

    def test_target_summary_shows_distance_and_visual_hit_chance(self):
        match = Game(map_size=20, window_size=9).create_match()
        shooter = match.pov
        target = match.teamList[1].squadsList[0].mechList[0]
        shooter.pos = [2, 10]
        target.pos = [10, 10]
        shooter.directlyVisibleEnemies = [target]
        weapon = shooter.mechClass.gunList[0]

        with patch("builtins.print") as print_mock:
            firing.printTargetingSummary(match, weapon, target)

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
            firing.printTargetingSummary(match, shooter.mechClass.gunList[0], target)

        output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("Hit chance:", output)

    def test_abilities_command_activates_the_selected_hull_ability(self):
        match = Game(map_size=20, window_size=9).create_match()
        match.pov.pos = [4, 4]
        for index, entity in enumerate(match.entities):
            if entity is not match.pov:
                entity.pos = [10 + index, 15]

        with patch("builtins.input", side_effect=["ab", "1", "d"]), patch("builtins.print"):
            dispatch.receive_input(match)

        self.assertEqual(match.pov.pos, [7, 4])
        self.assertEqual(match.pov.mechClass.hull.abilities[0].charges, 1)

    def test_launcher_target_selection_reopens_the_launcher_menu(self):
        match = Game(map_size=20, window_size=9).create_match()
        launcher_mech = next(
            mech for mech in match.teamList[0].squadsList[0].mechList
            if mech.pilot.name == "Chiki"
        )
        launcher = launcher_mech.mechClass.gunList[0]
        selected_target = match.teamList[1].squadsList[0].mechList[0]
        match.pov = launcher_mech
        original_menu = firing.launcherFireMenu

        with patch("builtins.input", return_value="t"), patch(
            "mechgame.commands.firing.chooseLauncherTrackedContact", return_value=selected_target
        ), patch("mechgame.commands.firing.launcherFireMenu") as reopened_menu:
            original_menu(match, launcher)

        reopened_menu.assert_called_once_with(match, launcher, selected_target)

    def test_launcher_auto_lead_projects_visual_contact_by_flight_time(self):
        match = Game(map_size=30, window_size=9).create_match()
        launcher_mech = next(
            mech for mech in match.teamList[0].squadsList[0].mechList
            if mech.pilot.name == "Chiki"
        )
        launcher = launcher_mech.mechClass.gunList[0]
        target = match.teamList[1].squadsList[0].mechList[0]
        match.pov = launcher_mech
        launcher_mech.pos = [4, 4]
        target.pos = [10, 10]
        target.turnStartPos = [8, 10]
        target.speed = 2
        launcher_mech.directlyVisibleEnemies = [target]

        self.assertEqual(firing.predictLauncherLead(match, launcher, target), [12, 10])
        self.assertIn("'L' auto lead", firing.launcherFirePrompt(match, launcher, target))

    def test_direct_fire_target_selection_reopens_the_full_target_menu(self):
        match = Game(map_size=20, window_size=9).create_match()
        default_target = match.teamList[1].squadsList[0].mechList[0]
        selected_target = match.teamList[1].squadsList[0].mechList[1]
        weapon = match.pov.mechClass.gunList[0]
        original_menu = firing.chooseFireTarget

        with patch("builtins.input", return_value="t"), patch(
            "mechgame.commands.firing.chooseTrackedContact", return_value=selected_target
        ), patch("mechgame.commands.firing.chooseFireTarget") as reopened_menu:
            original_menu(match, default_target, weapon)

        reopened_menu.assert_called_once_with(
            match, selected_target, weapon, promptDisplayed=True
        )

    def test_weapon_selection_keeps_radar_selected_target(self):
        match = Game(map_size=20, window_size=9).create_match()
        bastion = match.teamList[1].squadsList[0].mechList[0]
        selected_target = match.pov
        match.pov = bastion
        original_menu = firing.gunMenu

        with patch("builtins.input", return_value="1"), patch("mechgame.commands.firing.fire") as fire_mock:
            original_menu(match, selected_target)

        fire_mock.assert_called_once_with(match, selected_target)

    def test_non_explosive_launcher_ammo_hides_damage_in_its_profile(self):
        match = Game(map_size=20, window_size=9).create_match()
        mortar = next(
            mech for mech in match.teamList[0].squadsList[0].mechList
            if mech.pilot.name == "Chiki"
        )
        launcher = mortar.mechClass.gunList[0]
        launcher.select_ammo(1)  # Smoke is the second catalogued mortar shell.

        with patch("builtins.print") as print_mock:
            firing.printLauncherProfile(match, mortar, launcher, [10, 10])

        output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("Smoke", output)
        self.assertNotIn("damage", output)

    def test_help_lists_every_main_command_and_footer_prioritizes_abilities(self):
        match = SimpleNamespace(advTurn=True)
        with patch("builtins.print") as print_mock:
            squad.helpCommand(match)
        help_output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        for command in ("'fire'", "'r'", "'p'", "'rd'", "'ab'", "'look'", "'m'", "'st'", "'sq'", "'rep'", "'o'", "'n'", "'end'", "'?'"):
            self.assertIn(command, help_output)
        self.assertFalse(match.advTurn)

        with patch("builtins.print") as print_mock:
            tactical._print_tactical_footer(80)
        footer_output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("'ab' Abilities", footer_output)
        self.assertIn("'o'", footer_output)
        self.assertIn("Options", footer_output)
        self.assertIn("'n' Next", footer_output)
        self.assertNotIn("'st' status", footer_output)
