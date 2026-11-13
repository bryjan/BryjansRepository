"""Coverage for delayed launcher payloads and terrain effects."""

import random
import unittest
from unittest.mock import patch

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

    def test_zero_turn_shell_impacts_immediately_and_reports_its_launch(self):
        zero_turn_bands = {
            "close": [30, 0, 0],
            "medium": [50, 0, 0],
            "far": [80, 0, 0],
        }
        smoke = artillery.LauncherAmmo(
            "Test Smoke", zero_turn_bands, payload="smoke", charges=1,
            effectRadius=0, effectTurns=2,
        )
        launcher = WeaponLimb(
            "Test Launcher", 1, 1, [], 0, 0, 15, None,
            ammoTypes=[smoke],
        )
        listener = self.match.teamList[1].squadsList[0].mechList[0]
        listener.pos = [10, 10]

        launcher.launchAt(self.match, [8, 10])

        self.assertEqual(self.match.map[10][8].onSmoke, 1)
        self.assertEqual(self.match.pendingImpacts, [])
        self.assertTrue(any(
            "hear fire from a Test Launcher" in report[0]
            for report in listener.squad.reportLog
        ))

    def test_explosion_reports_are_critical_when_visually_confirmed(self):
        impact_cell = self.match.map[10][10]
        observer = self.match.pov
        listener = self.match.teamList[1].squadsList[0].mechList[0]
        observer.visibleCells = [impact_cell]
        listener.visibleCells = []
        listener.pos = [11, 10]

        self.match.explosion([10, 10], radius=0, size=0, damage=0, soundRange=15)

        self.assertTrue(any(
            critical and "see an explosion at [10, 10]" in report
            for report, critical, _ in observer.squad.reportLog
        ))
        self.assertTrue(any(
            not critical and "hear an explosion" in report
            for report, critical, _ in listener.squad.reportLog
        ))

    def test_fireproof_terrain_extinguishes_after_one_round_update(self):
        border_cell = self.match.map[0][0]
        effects.add_fire(border_cell)
        effects.advance_effects(self.match)

        self.assertEqual(border_cell.onFire, 0)

    def test_fire_damage_reports_critical_only_after_penetrating_armor(self):
        mech = self.match.pov
        limb = mech.mechClass.legs

        # The Lancer's legs have less than eight armor, so this fire hit
        # reaches HP and must be displayed as a critical warning.
        limb.damage(self.match, 8, "fire")
        self.assertTrue(any(
            critical and "hit by a fire" in report
            for report, critical, _ in mech.squad.reportLog
        ))

        mech.squad.reportLog.clear()
        limb.armor = 8
        limb.damage(self.match, 8, "fire")
        self.assertFalse(any("hit by a fire" in report for report, _, _ in mech.squad.reportLog))

    def test_fire_keeps_smoke_and_draws_above_it(self):
        cell = self.match.map[1][1]
        effects.add_fire(cell)

        self.assertEqual(effects.SmokeEffect.symbol, "~")
        self.assertTrue(any(isinstance(effect, effects.FireEffect) for effect in cell.effects))
        self.assertTrue(any(isinstance(effect, effects.SmokeEffect) for effect in cell.effects))

        with patch("mechgame.terrain.colored", side_effect=lambda symbol, *_: symbol), patch("builtins.print") as print_mock:
            cell.displayCell(self.match)
        self.assertEqual(print_mock.call_args.args[0], "*")
