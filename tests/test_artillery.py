"""Coverage for delayed launcher payloads and terrain effects."""

import random
import unittest

from mechgame import artillery, effects
from mechgame.mechs import WeaponLimb
from mechgame.runner import Game


class ArtilleryTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()
        self.match.pov.pos = [2, 10]
        self.bands = {
            "close": [30, 0, 1],
            "medium": [50, 0, 2],
            "far": [80, 0, 3],
        }

    def test_smoke_shell_creates_sensor_penalties_after_impact(self):
        smoke = artillery.LauncherAmmo(
            "Test Smoke", self.bands, payload="smoke", charges=1,
            effectRadius=0, effectTurns=2,
        )
        launcher = WeaponLimb(
            "Test Launcher", 1, 1, [], 0, 0, 1, None,
            ammoTypes=[smoke],
        )

        launcher.launchAt(self.match, [10, 10])
        # Launcher travel time starts after the firing squad's current turn.
        artillery.advance_impacts(self.match)
        artillery.advance_impacts(self.match)
        impact_cell = self.match.map[10][10]

        self.assertEqual(impact_cell.onSmoke, 1)
        self.assertEqual(impact_cell.visualAbsorption, impact_cell.terrain.visAbsorb + 12)
        self.assertEqual(impact_cell.radarAbsorption, impact_cell.terrain.radarAbsorb + 2)

    def test_one_turn_shell_waits_through_a_complete_future_squad_turn(self):
        smoke = artillery.LauncherAmmo(
            "Test Smoke", self.bands, payload="smoke", charges=1,
            effectRadius=0, effectTurns=2,
        )
        launcher = WeaponLimb(
            "Test Launcher", 1, 1, [], 0, 0, 1, None,
            ammoTypes=[smoke],
        )

        launcher.launchAt(self.match, [10, 10])
        impact_cell = self.match.map[10][10]

        # Ending the firing squad's turn starts the enemy turn, but the shell
        # has not yet spent its one configured future turn in flight.
        self.match.nextSquadTurn()
        self.assertEqual(impact_cell.onSmoke, 0)

        # It lands as the following squad turn begins.
        self.match.nextSquadTurn()
        self.assertEqual(impact_cell.onSmoke, 1)

    def test_fireproof_terrain_extinguishes_after_one_round_update(self):
        border_cell = self.match.map[0][0]
        effects.add_fire(border_cell)
        effects.advance_effects(self.match)

        self.assertEqual(border_cell.onFire, 0)
