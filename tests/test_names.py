import random
import unittest

from mechgame.entities import Pilot
from mechgame.names import (
    FIRST_NAMES, LAST_NAMES, NICKNAMES, PRESET_PILOT_NAMES,
    generate_random_name, generate_random_nickname,
)


class PilotNamingTests(unittest.TestCase):
    def test_display_name_prefers_callsign_then_nickname_then_name(self):
        pilot = Pilot("Avery Archer")
        self.assertEqual(pilot.display_name, "Avery Archer")

        pilot.assign_nickname("Sparrow")
        self.assertEqual(pilot.display_name, 'Avery "Sparrow"')

        pilot.assign_callsign("Viper")
        self.assertEqual(pilot.display_name, "Viper")

        pilot.assign_callsign(None)
        self.assertEqual(pilot.display_name, 'Avery "Sparrow"')

    def test_long_nickname_displays_without_first_name_when_it_would_not_fit(self):
        pilot = Pilot("Avery Archer", nickname="LongNickname")

        self.assertEqual(pilot.display_name, '"LongNickname"')

    def test_nickname_visibility_can_be_toggled_without_removing_an_earned_nickname(self):
        pilot = Pilot("Avery Archer", nickname="Ash")

        self.assertFalse(pilot.toggle_nickname_visibility())
        self.assertEqual(pilot.nickname, "Ash")
        self.assertEqual(pilot.display_name, "Avery Archer")

    def test_name_assigners_normalize_input_and_reject_blank_legal_names(self):
        pilot = Pilot("Avery Archer")
        pilot.assign_name("  Dara Dawson  ")
        pilot.assign_nickname("  Drift  ")

        self.assertEqual(pilot.name, "Dara Dawson")
        self.assertEqual(pilot.nickname, "Drift")
        with self.assertRaisesRegex(ValueError, "cannot be blank"):
            pilot.assign_name("  ")

    def test_random_name_generator_avoids_previously_used_names(self):
        rng = random.Random(7)
        first = generate_random_name(rng)
        second = generate_random_name(rng, [first])

        self.assertNotEqual(first, second)

    def test_random_nickname_generator_avoids_previously_used_nicknames(self):
        rng = random.Random(9)
        first = generate_random_nickname(rng)
        second = generate_random_nickname(rng, [first])

        self.assertIn(first, NICKNAMES)
        self.assertIn(second, NICKNAMES)
        self.assertNotEqual(first, second)

    def test_preset_skirmish_pilots_are_part_of_the_random_name_pool(self):
        # Using every generated name as already-used leaves presets as the
        # only candidates, proving they are available to future campaigns.
        generated_names = {f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES}
        name = generate_random_name(random.Random(0), generated_names)

        self.assertIn(name, PRESET_PILOT_NAMES)
