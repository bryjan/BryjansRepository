"""Regression tests for the lightweight demo entry menu."""

import unittest

from mechgame.menu import show_start_menu


class StartMenuTests(unittest.TestCase):
    """Verify that the menu makes a clear start-or-quit decision."""

    def test_blank_choice_starts_a_match(self):
        output = []

        self.assertTrue(show_start_menu(lambda _: "", output.append))
        self.assertEqual(output[1], "+" + ("-" * 70) + "+")
        self.assertIn("'Enter' or '1' Start random skirmish", "\n".join(output))

    def test_help_can_be_followed_by_quit(self):
        choices = iter(("?", "", "q"))
        output = []

        self.assertFalse(show_start_menu(lambda _: next(choices), output.append))
        rendered = "\n".join(output)
        self.assertIn("DEMO ROSTER", rendered)
        self.assertIn("DESTRUCTION", rendered)


if __name__ == "__main__":
    unittest.main()
