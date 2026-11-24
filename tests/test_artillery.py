"""Coverage for delayed launcher payloads and terrain effects."""

import random
import unittest
from unittest.mock import patch

from mechgame import artillery, effects
from mechgame.mechs import WeaponLimb
from mechgame.runner import Game
from mechgame.teams import Squad


class ArtilleryTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
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
        # Merely handing off between squads cannot advance a match round.
        artillery.advance_impacts(self.match)
        self.assertEqual(self.match.map[10][10].onSmoke, 0)
        self.match.matchRound += 1
        artillery.advance_impacts(self.match)
        impact_cell = self.match.map[10][10]

        self.assertEqual(impact_cell.onSmoke, 1)
        self.assertEqual(impact_cell.visualAbsorption, impact_cell.terrain.visAbsorb + 12)
        self.assertEqual(impact_cell.radarAbsorption, impact_cell.terrain.radarAbsorb + 2)

    def test_chaff_obscures_radar_more_than_visuals(self):
        cell = self.match.map[10][10]
        effects.add_chaff(cell)

        self.assertEqual(cell.onChaff, 1)
        self.assertEqual(cell.visualAbsorption, cell.terrain.visAbsorb + 3)
        self.assertEqual(cell.radarAbsorption, cell.terrain.radarAbsorb + 12)

    def test_mountain_depth_extends_launcher_range_by_one_or_two_tiles(self):
        launcher = WeaponLimb(
            "Test Launcher", 1, 1, [], 0, 0, 1, None,
            ammoTypes=[artillery.LauncherAmmo("Test", self.bands)],
        )
        self.match.pov.pos = [4, 4]
        self.match.map[4][4].terrain = self.match.mountain

        self.assertEqual(launcher.launcher_range_bonus(self.match, self.match.pov), 1)
        self.assertIsNotNone(launcher.launcher_profile(81, self.match, self.match.pov))

        for y in range(3, 6):
            for x in range(3, 6):
                self.match.map[y][x].terrain = self.match.mountain
        self.assertEqual(launcher.launcher_range_bonus(self.match, self.match.pov), 2)
        self.assertIsNotNone(launcher.launcher_profile(82, self.match, self.match.pov))

    def test_one_round_shell_waits_through_the_enemy_phase(self):
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

        # The enemy phase is still round 0, so the shell remains in flight.
        self.match.nextSquadTurn()
        self.assertEqual(impact_cell.onSmoke, 0)

        # It lands when round 1 begins, after the enemy phase completes.
        self.match.nextSquadTurn()
        self.assertEqual(impact_cell.onSmoke, 1)

    def test_three_round_shell_does_not_land_during_five_squad_handoffs(self):
        player, enemy = self.match.teamList
        reserve_mech = player.squadsList[0].mechList.pop()
        reserve = Squad("Reserve", [reserve_mech], "Combat", playerControlled=True)
        reserve.team = player
        player.squadsList.append(reserve)
        original = enemy.squadsList[0]
        units = list(original.mechList)
        enemy.squadsList = []
        for index, unit in enumerate(units):
            squad = Squad(f"Enemy {index}", [unit], "Combat")
            squad.team = enemy
            enemy.squadsList.append(squad)
        bands = {name: [distance, 0, 3] for name, distance in (("close", 30), ("medium", 50), ("far", 80))}
        launcher = WeaponLimb("Three-round mortar", 1, 1, [], 0, 0, 1, None,
                              ammoTypes=[artillery.LauncherAmmo("Smoke", bands, payload="smoke", charges=1, effectRadius=0)])
        launcher.launchAt(self.match, [10, 10])
        with patch("mechgame.artillery.resolve_impact", wraps=artillery.resolve_impact) as resolve:
            for _ in range(14):
                self.match.nextSquadTurn()
                resolve.assert_not_called()
                self.assertEqual(self.match.map[10][10].onSmoke, 0)
            self.assertEqual(self.match.matchRound, 2)
            self.match.nextSquadTurn()
            self.assertEqual(self.match.matchRound, 3)
            resolve.assert_called_once()
            self.assertEqual(self.match.map[10][10].onSmoke, 1)

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

    def test_mech_in_explosion_reports_being_hit_not_seeing_it(self):
        impact_cell = self.match.map[10][10]
        victim = self.match.teamList[1].squadsList[0].mechList[0]
        victim.pos = [10, 10]
        victim.visibleCells = [impact_cell]

        self.match.explosion([10, 10], radius=0, size=0, damage=0)

        self.assertTrue(any(
            critical and "caught in an explosion" in report
            for report, critical, _ in victim.squad.reportLog
        ))
        self.assertFalse(any(
            "see an explosion" in report
            for report, _, _ in victim.squad.reportLog
        ))

    def test_fireproof_terrain_extinguishes_after_one_round_update(self):
        border_cell = self.match.map[0][0]
        effects.add_fire(border_cell)
        effects.advance_effects(self.match)

        self.assertEqual(border_cell.onFire, 0)

    def test_mountain_fire_is_not_immediately_extinguished_as_fireproof_terrain(self):
        mountain_cell = self.match.map[10][10]
        mountain_cell.terrain = self.match.mountain
        effects.add_fire(mountain_cell, turns=2)

        with patch.object(self.match.rng, "random", return_value=1.0):
            effects.advance_effects(self.match)

        self.assertEqual(mountain_cell.onFire, 1)

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
