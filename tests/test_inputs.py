import unittest
from types import SimpleNamespace
from unittest.mock import patch

import inputs


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
