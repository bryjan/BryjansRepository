import random
import unittest

from mechgame import effects
from mechgame.match import MatchInfo
from mechgame.runner import Game
from mechgame.catalog import create_mech
from mechgame.world import MapGenerator


class MapGeneratorTests(unittest.TestCase):
    def test_generator_creates_square_map_with_a_border(self):
        match = MatchInfo(12, 9, [], "")
        match.map = MapGenerator(12, random.Random(0)).build(match)

        self.assertEqual(len(match.map), 12)
        self.assertTrue(all(len(row) == 12 for row in match.map))
        self.assertTrue(all(cell.terrain is match.border for cell in match.map[0]))
        self.assertTrue(all(row[0].terrain is match.border for row in match.map))

    def test_map_init_uses_the_world_generator(self):
        match = MatchInfo(12, 9, [], "")
        match.mapInit()

        self.assertTrue(match.map[6][6].nList)

    def test_game_creates_a_small_match(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()

        self.assertEqual(len(match.entities), 8)
        self.assertEqual(match.pov.pilot.name, "B")

        self.assertEqual(
            [mech.mechClass.name for mech in match.teamList[0].squadsList[0].mechList],
            [
                "Lancer Type.S Pathfinder",
                "Lancer Type.A",
                "Lancer Type.A",
                "Lancer Type.A",
                "Lancer Type.M Mortar",
            ],
        )
        self.assertEqual(
            [mech.mechClass.name for mech in match.teamList[1].squadsList[0].mechList],
            ["Bastion", "Kestrel", "Bastion"],
        )

    def test_squad_roster_lists_pilots_mechs_and_positions(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()

        roster = match.pov.squad.rosterReport()

        self.assertIn("B — Lancer Type.S Pathfinder", roster)
        self.assertIn("115um6uy15 — Lancer Type.A", roster)
        self.assertIn("at [", roster)

    def test_standard_lancer_has_short_range_plasma_lance(self):
        lancer = create_mech("lancer.type_a")
        lance = next(weapon for weapon in lancer.gunList if weapon.name == "Plasma Lance")

        self.assertTrue(lance.isMelee)
        self.assertEqual(lance.maxRange, 1.5)
        self.assertEqual(lance.accuracy, 13)
        self.assertEqual(lance.dmg, 18)
        self.assertTrue(lance.piercing)
        self.assertEqual(lance.energyCost, 0)
        self.assertEqual(lance.aim_ap_cost(lancer.helm), 0)

    def test_lancer_hull_dash_crosses_restrictive_terrain_without_cost(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()
        lancer = match.pov
        dash = lancer.mechClass.hull.abilities[0]
        lancer.pos = [4, 4]
        lancer.energy = 0
        lancer.mp = 0
        match.map[4][5].terrain = match.forest

        self.assertTrue(dash.use(match, lancer, "d"))
        self.assertEqual(lancer.pos, [7, 4])
        self.assertEqual(lancer.energy, 0)
        self.assertEqual(lancer.mp, 0)
        self.assertEqual(lancer.speed, 3)
        self.assertEqual(dash.charges, 1)
        for x in (5, 6, 7):
            trail_effects = match.map[4][x].effects
            self.assertTrue(any(isinstance(effect, effects.SmokeEffect) for effect in trail_effects))
            self.assertTrue(any(isinstance(effect, effects.ChaffEffect) for effect in trail_effects))

    def test_dash_boosts_plasma_lance_damage_until_turn_end(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()
        lancer = match.teamList[0].squadsList[0].mechList[1]
        lancer.pos = [4, 4]
        dash = lancer.mechClass.hull.abilities[0]
        lance = next(weapon for weapon in lancer.mechClass.gunList if weapon.isMelee)

        self.assertTrue(dash.use(match, lancer, "d"))
        self.assertEqual(lance.dmg, 21)

        lancer.clearTurnAbilities()
        self.assertEqual(lance.dmg, 18)

    def test_kestrel_sensor_overdrive_boosts_and_then_clears_sensors(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()
        kestrel = match.teamList[1].squadsList[0].mechList[1]
        overdrive = kestrel.mechClass.hull.abilities[0]
        starting_energy = kestrel.energy
        base_visual = kestrel.mechClass.visPower
        base_radar = kestrel.mechClass.radarPower

        self.assertTrue(overdrive.use(match, kestrel))
        self.assertEqual(kestrel.energy, starting_energy - 4)
        self.assertEqual(kestrel.visPower, int(base_visual * 1.4))
        self.assertEqual(kestrel.radarPower, int(base_radar * 1.4))
        self.assertTrue(kestrel.radarPulseActive)

        kestrel.clearTurnAbilities()
        self.assertEqual(kestrel.visPower, base_visual)
        self.assertEqual(kestrel.sensorBoostMultiplier, 1)

    def test_bastion_field_repair_restores_parts_and_modules(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()
        bastion = match.teamList[1].squadsList[0].mechList[0]
        repair = bastion.mechClass.hull.abilities[0]
        legs, hull = bastion.mechClass.legs, bastion.mechClass.hull
        legs.hp, legs.armor, legs.limbCon = 1, 0, 0.1
        hull.hp, hull.armor, hull.limbCon = 2, 0, 0.2
        destroyed_module = hull.modsList[0]
        damaged_module = hull.modsList[1]
        destroyed_module.status = 0
        damaged_module.status = 1

        self.assertTrue(repair.use(match, bastion))
        self.assertEqual(legs.hp, legs.startingHP)
        self.assertEqual(hull.armor, hull.startingArmor)
        self.assertEqual(destroyed_module.status, 1)
        self.assertEqual(damaged_module.status, 2)
        self.assertEqual(bastion.ap, 0)
        self.assertEqual(repair.charges, 0)

    def test_bastion_heavy_beam_accuracy_is_reduced(self):
        bastion = create_mech("bastion")
        beam = next(weapon for weapon in bastion.gunList if weapon.name == "Heavy Melting Beam")

        self.assertEqual(beam.accuracy, 27)

    def test_squad_ammo_report_uses_each_mechs_average_ammo_percent(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()

        report = match.pov.squad.statusReport()

        self.assertIn("Ammo readiness:", report)
        self.assertIn("MagikP 100%", report)
        self.assertIn("Chiki 100%", report)
        self.assertNotIn("ChainGun", report)
        self.assertNotIn("Plasma Lance", report)
