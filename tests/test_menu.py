import unittest
from unittest.mock import patch

from mechgame.runner import Game
from mechgame.ui.menu import DisplaySettings, start_menu
from mechgame.ui.tactical import MIN_TACTICAL_HEIGHT


class StartMenuTests(unittest.TestCase):
    def test_skirmish_uses_display_options_selected_before_starting(self):
        settings = DisplaySettings()
        with patch("builtins.input", side_effect=["o", "w", "25", "h", "21", "x", "s"]), patch("builtins.print"):
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
