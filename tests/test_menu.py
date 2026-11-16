import unittest
from types import SimpleNamespace
from unittest.mock import patch

import main as application
from mechgame.runner import Game
from mechgame.ui.menu import DisplaySettings, _frame_lines, start_menu
from mechgame.ui.tactical import DEFAULT_TACTICAL_SIZE, MIN_TACTICAL_HEIGHT
from mechgame.world import CUSTOM_MAP_PRESET, get_map_preset


class StartMenuTests(unittest.TestCase):
    def test_main_reopens_the_start_menu_after_a_match_returns(self):
        settings = DisplaySettings()
        with patch("main.start_menu", side_effect=[settings, None]), patch("main.Game") as game:
            game.return_value.run.return_value = SimpleNamespace(quitRequested=True)
            application.main()

        game.assert_called_once_with(
            window_width=settings.tactical_width,
            window_height=settings.tactical_height,
            terrain_enabled=settings.terrain_enabled,
            map_preset=settings.map_preset,
        )
        game.return_value.run.assert_called_once_with()

    def test_skirmish_uses_display_options_selected_before_starting(self):
        settings = DisplaySettings()
        with patch("builtins.input", side_effect=["o", "d", "w", "25", "h", "21", "x", "x", "s"]), patch("builtins.print"):
            selected = start_menu(settings)

        self.assertIs(selected, settings)
        self.assertEqual(settings.tactical_width, 25)
        self.assertEqual(settings.tactical_height, 21)

        match = Game(
            map_size=30,
            window_width=settings.tactical_width,
            window_height=settings.tactical_height,
        ).create_match()
        self.assertEqual(match.windowWidth, 25)
        self.assertEqual(match.windowHeight, 21)

    def test_quit_returns_none(self):
        with patch("builtins.input", return_value="q"), patch("builtins.print"):
            self.assertIsNone(start_menu())

    def test_default_height_meets_the_tactical_panel_minimum(self):
        self.assertGreaterEqual(DisplaySettings().tactical_height, MIN_TACTICAL_HEIGHT)

    def test_default_tactical_view_is_thirty_seven_by_thirty_seven(self):
        settings = DisplaySettings()
        match = Game(map_size=40).create_match()

        self.assertEqual(settings.tactical_width, DEFAULT_TACTICAL_SIZE)
        self.assertEqual(settings.tactical_height, DEFAULT_TACTICAL_SIZE)
        self.assertEqual((match.windowWidth, match.windowHeight), (37, 37))

    def test_map_tile_menu_can_enable_urban_generation(self):
        settings = DisplaySettings()
        self.assertTrue(settings.terrain_enabled["urban"])

        with patch("builtins.input", side_effect=["o", "m", "5", "x", "x", "s"]), patch("builtins.print"):
            selected = start_menu(settings)

        self.assertIs(selected, settings)
        self.assertFalse(settings.terrain_enabled["urban"])
        self.assertEqual(settings.map_preset, CUSTOM_MAP_PRESET)

    def test_map_tile_menu_can_disable_river_generation(self):
        settings = DisplaySettings()
        self.assertTrue(settings.terrain_enabled["river"])

        with patch("builtins.input", side_effect=["o", "m", "8", "x", "x", "s"]), patch("builtins.print"):
            selected = start_menu(settings)

        self.assertIs(selected, settings)
        self.assertFalse(settings.terrain_enabled["river"])
        self.assertEqual(settings.map_preset, CUSTOM_MAP_PRESET)

    def test_map_preset_replaces_tile_choices_with_its_own_configuration(self):
        settings = DisplaySettings()
        with patch("builtins.input", side_effect=["o", "p", "2", "x", "s"]), patch("builtins.print"):
            selected = start_menu(settings)

        self.assertIs(selected, settings)
        self.assertEqual(settings.map_preset, "badlands")
        self.assertEqual(settings.terrain_enabled, get_map_preset("badlands").terrain_options())

    def test_all_start_menu_pages_follow_the_selected_screen_size(self):
        settings = DisplaySettings(tactical_width=25, tactical_height=21)
        main_frame = _frame_lines(["ASCII MECH GAME", "'s' Skirmish"], settings)
        options_frame = _frame_lines(["OPTIONS", "'d' Display size"], settings)

        self.assertEqual(len(main_frame), 23)
        self.assertEqual(len(options_frame), 23)
        self.assertTrue(all(len(line) == 54 for line in main_frame))
        self.assertTrue(all(len(line) == 54 for line in options_frame))
