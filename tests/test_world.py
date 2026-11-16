import random
import unittest

from mechgame import effects
from mechgame.match import MatchInfo
from mechgame.mechs import Helm, Hull, Legs, MechClass, MechPart, Module
from mechgame.runner import Game
from mechgame.catalog import create_mech
from mechgame.terrain import TerrainType
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

    def test_generator_rejects_maps_that_cannot_draw_a_road(self):
        with self.assertRaisesRegex(ValueError, "at least 8"):
            MapGenerator(7).build(MatchInfo(7, 7, [], ""))

    def test_terrain_defaults_are_not_shared_between_instances(self):
        first = TerrainType("first", "1", "white")
        second = TerrainType("second", "2", "white")

        first.moveCost.append(1)
        first.symbolAttribute.append("bold")

        self.assertEqual(second.moveCost, [])
        self.assertEqual(second.symbolAttribute, [])

    def test_urban_centers_provide_dense_cover_and_limit_large_mechs(self):
        match = MatchInfo(20, 9, [], "")
        match.map = MapGenerator(
            20, random.Random(0), terrain_enabled={"urban": True},
        ).build(match)

        self.assertEqual(match.urban.name, "urban center")
        self.assertEqual(match.urban.symbol, "#")
        self.assertEqual(match.urban.moveCost, [0, 0, 0, 1, 3, 9999, 9999])
        self.assertEqual(match.urban.visAbsorb, 30)
        self.assertEqual(match.urban.radarAbsorb, 60)
        self.assertTrue(any(cell.terrain is match.urban for row in match.map for cell in row))

    def test_optional_terrain_can_be_disabled_or_left_out_by_default(self):
        match = MatchInfo(20, 9, [], "")
        match.map = MapGenerator(20, random.Random(0)).build(match)

        self.assertFalse(any(cell.terrain is match.urban for row in match.map for cell in row))

        disabled = MatchInfo(20, 9, [], "")
        disabled.map = MapGenerator(
            20, random.Random(0),
            terrain_enabled={"forest": False, "desert": False, "road": False, "suburb": False},
        ).build(disabled)
        self.assertTrue(all(cell.terrain in (disabled.border, disabled.plains) for row in disabled.map for cell in row))

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

    def test_seeded_games_reproduce_terrain_and_spawn_positions(self):
        first = Game(map_size=20, window_size=9, rng=random.Random(7)).create_match()
        second = Game(map_size=20, window_size=9, rng=random.Random(7)).create_match()

        first_terrain = [[cell.terrain.name for cell in row] for row in first.map]
        second_terrain = [[cell.terrain.name for cell in row] for row in second.map]

        self.assertEqual(first_terrain, second_terrain)
        self.assertEqual(
            [mech.pos for mech in first.entities],
            [mech.pos for mech in second.entities],
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

    def test_flying_legs_enable_flight_and_charge_flight_energy(self):
        flying_mech = MechClass(
            "Test Flyer", "F", "white",
            Hull("Hull", 1, 1, [], 10, 1, 1, 2),
            Helm("Helm", 1, 1, [], 1, 1, 0),
            Legs("Flight Legs", 1, 1, [], 2, fly=True),
        )
        self.assertTrue(flying_mech.initFlying)

        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()
        flyer = match.pov
        flyer.pos = [4, 4]
        flyer.flying = True
        flyer.energy = 4
        match.entities = [flyer]
        match.map[4][5].terrain = match.road

        flyer.moveMech(match, "d")

        self.assertEqual(flyer.energy, 2)

    def test_incompatible_module_does_not_block_later_module_updates(self):
        incompatible = Module("Wrong Target", ["missingStat"], 1, [[0, 0, 0]])
        compatible = Module("Armor Bonus", ["bonusArmor"], 1, [[0, 1, 2]])

        part = MechPart("Test Part", 1, 1, [incompatible, compatible])

        self.assertEqual(part.bonusArmor, 2)

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

        lancer = next(mech for mech in match.pov.squad.mechList if mech.pilot.name == "MagikP")
        chain_gun = next(weapon for weapon in lancer.mechClass.gunList if weapon.name == "ChainGun")
        chain_gun.charges = 0

        self.assertIn("MagikP 50%", match.pov.squad.statusReport())
