from collections import Counter
import math
import random
import unittest
from unittest.mock import patch

from mechgame import effects
from mechgame.match import MatchInfo
from mechgame.mechs import Helm, Hull, Legs, MechClass, MechPart, Module
from mechgame.runner import Game
from mechgame.catalog import create_mech
from mechgame.terrain import TerrainType
from mechgame.world import (
    CUSTOM_MAP_PRESET,
    DEFAULT_MAP_PRESET,
    DEFAULT_TERRAIN_ENABLED,
    MAP_PRESETS,
    MapFeatures,
    MapGenerator,
    get_map_preset,
)


class MapGeneratorTests(unittest.TestCase):
    def test_terrain_features_register_bridges_mountain_entries_and_intersections(self):
        match = MatchInfo(12, 9, [], "")
        generator = MapGenerator(12, random.Random(0))
        grid = generator.build(match)
        for row in grid[1:-1]:
            for cell in row[1:-1]:
                cell.terrain = match.plains

        generator.features = MapFeatures()
        generator.features.add_road("road", [(3, 4), (4, 4), (3, 10)])
        generator.features.add_road("road", [(3, 3), (3, 4), (3, 5)])
        generator.features.add_river("small_river", [(3, 10)])
        generator.features.refresh_bridges()

        # This road first touches the range at [4, 4].
        grid[4][5].terrain = match.mountain
        generator._identify_terrain_locations(grid, {
            "mountain": match.mountain,
        })

        locations_by_kind = {
            location.kind: location
            for location in generator.features.tactical_locations
        }
        self.assertEqual(locations_by_kind["bridge"].tiles, ((3, 10),))
        self.assertEqual(locations_by_kind["bridge"].marker_tiles, ((3, 10),))
        self.assertEqual(locations_by_kind["road_intersection"].tiles, ((3, 4),))
        self.assertIn((4, 4), locations_by_kind["mountain_entrance"].tiles)

    def test_map_features_preserve_routes_and_accept_scenario_locations(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        features = match.mapFeatures

        self.assertTrue(features.roads)
        self.assertTrue(all(route.tiles for route in features.roads))
        self.assertEqual(
            [route.route_id for route in features.roads],
            [f"road_{index}" for index in range(1, len(features.roads) + 1)],
        )

        features.add_objective("relay", "Relay Station", "capture", [(12, 12)])
        features.add_tactical_location("ford", "River Crossing", "crossing", [(13, 12)])

        self.assertEqual(features.objectives[0].name, "Relay Station")
        self.assertEqual(features.tactical_locations[-1].kind, "crossing")
        self.assertEqual(features.tactical_locations[-1].marker_tiles, ((13, 12),))

    def test_teams_get_independent_future_map_visibility_flags(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        player_team, enemy_team = match.teamList

        flags = player_team.mapVisibility
        self.assertTrue(flags.debug_reveal_all)
        self.assertTrue(flags.show_all_terrain)
        self.assertTrue(flags.show_all_objectives)
        self.assertFalse(flags.remember_explored_terrain)
        self.assertTrue(flags.show_friendly_entities)
        self.assertTrue(flags.show_visual_enemies)
        self.assertTrue(flags.show_radar_contacts)
        self.assertTrue(flags.show_known_effects)

        flags.debug_reveal_all = False
        self.assertTrue(enemy_team.mapVisibility.debug_reveal_all)

    def test_generator_creates_square_map_with_a_border(self):
        match = MatchInfo(12, 9, [], "")
        match.map = MapGenerator(12, random.Random(0)).build(match)

        self.assertEqual(len(match.map), 12)
        self.assertTrue(all(len(row) == 12 for row in match.map))
        self.assertTrue(all(cell.terrain is match.border for cell in match.map[0]))
        self.assertTrue(all(row[0].terrain is match.border for row in match.map))

    def test_desert_has_subtle_heat_haze_without_extra_radar_cover(self):
        match = MatchInfo(12, 9, [], "")
        MapGenerator(12, random.Random(0)).build(match)

        self.assertEqual(match.desert.visAbsorb, 1.2)
        self.assertEqual(match.desert.radarAbsorb, match.plains.radarAbsorb)

    def test_named_presets_define_complete_terrain_only_map_profiles(self):
        self.assertEqual(get_map_preset(DEFAULT_MAP_PRESET).terrain_options(), DEFAULT_TERRAIN_ENABLED)
        self.assertEqual(len({preset.key for preset in MAP_PRESETS}), len(MAP_PRESETS))

        badlands = MapGenerator(20, random.Random(0), map_preset="badlands")
        self.assertEqual(badlands.map_preset.desert_density, "Dominant")
        self.assertEqual(badlands.map_preset.mountain_weight, 1.5)
        self.assertFalse(badlands.terrain_enabled["forest"])
        self.assertFalse(badlands.terrain_enabled["water"])

        river_basin = MapGenerator(20, random.Random(0), map_preset="river_basin")
        self.assertGreater(river_basin.map_preset.large_river_weight, 1)
        self.assertGreater(river_basin.map_preset.small_river_weight, 1)
        self.assertTrue(river_basin.terrain_enabled["river"])

        frontier = MapGenerator(20, random.Random(0), map_preset=DEFAULT_MAP_PRESET)
        self.assertEqual(frontier.map_preset.road_density, "Normal")
        self.assertEqual(frontier.map_preset.highway_count, 1)
        self.assertEqual(frontier.map_preset.suburb_offshoot_count, 1)
        self.assertEqual(frontier.map_preset.forest_extra_growth, 2)

        urban_fringe = MapGenerator(20, random.Random(0), map_preset="urban_fringe")
        self.assertEqual(urban_fringe.map_preset.suburb_cluster_multiplier, 5)
        self.assertEqual(urban_fringe.map_preset.urban_cluster_multiplier, 5)

    def test_custom_terrain_toggles_retain_temperate_generation_weights(self):
        generator = MapGenerator(
            20,
            random.Random(0),
            terrain_enabled={"urban": False},
            map_preset=CUSTOM_MAP_PRESET,
        )

        self.assertEqual(generator.map_preset.key, DEFAULT_MAP_PRESET)
        self.assertFalse(generator.terrain_enabled["urban"])
        self.assertEqual(generator.map_preset.road_density, "Normal")

    def test_unknown_map_preset_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown map preset"):
            MapGenerator(20, random.Random(0), map_preset="not-a-preset")

    def test_presets_apply_distinct_terrain_generation_weights(self):
        def terrain_counts(preset):
            match = MatchInfo(100, 9, [], "")
            grid = MapGenerator(
                100, 100, random.Random(0), map_preset=preset,
            ).build(match)
            return Counter(cell.terrain.name for row in grid for cell in row)

        temperate = terrain_counts(DEFAULT_MAP_PRESET)
        badlands = terrain_counts("badlands")
        river_basin = terrain_counts("river_basin")
        urban_fringe = terrain_counts("urban_fringe")

        self.assertGreater(badlands["desert"], temperate["desert"] * 5)
        self.assertGreater(badlands["desert"], badlands["plains"] * 3)
        self.assertGreater(temperate["forest"], 700)
        self.assertGreaterEqual(temperate["suburbs"], 6)
        self.assertGreater(river_basin["water"], urban_fringe["water"])

    def test_game_forwards_its_map_preset_to_world_generation(self):
        match = Game(
            map_size=40,
            window_size=9,
            rng=random.Random(0),
            map_preset="urban_fringe",
        ).create_match()

        disabled_terrain = {"desert", "mountain", "water"}
        self.assertFalse(any(
            cell.terrain.name in disabled_terrain
            for row in match.map for cell in row
        ))

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

    def test_mountains_are_optional_clustered_cover_with_size_scaled_costs(self):
        match = MatchInfo(20, 9, [], "")
        match.map = MapGenerator(
            20, random.Random(0), terrain_enabled={"mountain": True},
        ).build(match)

        self.assertEqual(match.mountain.symbol, "^")
        self.assertEqual(match.mountain.moveCost, [6, 5, 4, 3, 2, 2, 2])
        self.assertEqual(match.mountain.visAbsorb, 12)
        self.assertEqual(match.mountain.radarAbsorb, 20)
        self.assertFalse(match.mountain.fireproof)
        self.assertTrue(any(cell.terrain is match.mountain for row in match.map for cell in row))

    def test_water_is_sensor_clear_and_uses_float_or_titanic_movement_rules(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        mech = match.pov
        mech.pos = [4, 4]
        water = match.map[4][5]
        water.terrain = match.water

        self.assertEqual(match.water.visAbsorb, 0)
        self.assertEqual(match.water.radarAbsorb, 0)
        self.assertEqual(match.water.moveCost, [1, 1, 1, 2, 3, 4, 5])

        with patch("builtins.print"):
            mech.moveMech(match, "d")
        self.assertEqual(mech.pos, [4, 4])

        mech.mechClass.canFloat = True
        mech.energy = 1
        mech.moveMech(match, "d")
        self.assertEqual(mech.pos, [5, 4])
        self.assertEqual(mech.energy, 0)

        mech.pos = [4, 4]
        mech.mechClass.canFloat = False
        mech.size = 6
        mech.energy = 5
        mech.moveMech(match, "d")
        self.assertEqual(mech.pos, [5, 4])
        self.assertEqual(mech.energy, 0)

    def test_water_toggle_generates_sparse_ponds_without_rivers(self):
        disabled = MatchInfo(50, 9, [], "")
        disabled.map = MapGenerator(
            50, random.Random(0), terrain_enabled={"water": False, "river": False},
        ).build(disabled)
        self.assertFalse(any(cell.terrain is disabled.water for row in disabled.map for cell in row))

        enabled = MatchInfo(50, 9, [], "")
        enabled.map = MapGenerator(
            50, random.Random(0), terrain_enabled={"water": True, "river": False},
        ).build(enabled)
        self.assertTrue(enabled.map)

    def test_water_patch_can_replace_a_mountain_tile(self):
        match = MatchInfo(12, 9, [], "")
        generator = MapGenerator(12, random.Random(0))
        grid = generator.build(match)
        seed = grid[6][6]
        seed.terrain = match.mountain

        generator._grow_water_patch(grid, seed, match.water, 3)

        self.assertIs(seed.terrain, match.water)

    def test_large_river_crosses_the_map_edge_to_edge_at_default_width(self):
        match = MatchInfo(20, 9, [], "")
        generator = MapGenerator(20, random.Random(0))
        grid = generator.build(match)

        generator._large_river(grid, match.water)

        water_columns = {
            x
            for row in grid for x, cell in enumerate(row)
            if cell.terrain is match.water
        }
        water_rows = {
            y
            for y, row in enumerate(grid) for cell in row
            if cell.terrain is match.water
        }
        self.assertTrue(
            ({1, generator.width - 2} <= water_columns)
            or ({1, generator.height - 2} <= water_rows)
        )

    def test_large_river_count_scales_with_map_span_not_area(self):
        normal = MapGenerator(100, random.Random(0))
        huge = MapGenerator(400, random.Random(0))

        self.assertEqual(normal._scaled_linear_feature_count(100), 1)
        self.assertGreater(huge._scaled_linear_feature_count(100), 1)

    def test_lakes_grow_from_a_large_river_bank(self):
        match = MatchInfo(30, 9, [], "")
        generator = MapGenerator(30, random.Random(0))
        grid = generator.build(match)
        river_cells = generator._large_river(grid, match.water)
        lake_cells = generator._lake_beside_large_river(grid, match.water, river_cells)

        self.assertGreaterEqual(len(lake_cells), 16)
        self.assertTrue(any(
            neighbor in river_cells
            for cell in lake_cells
            for neighbor in cell.nList
        ))

    def test_mountain_edges_can_grow_a_sparse_forest_fringe(self):
        match = MatchInfo(12, 9, [], "")
        generator = MapGenerator(12, random.Random(0))
        grid = generator.build(match)
        for row in grid[1:-1]:
            for cell in row[1:-1]:
                cell.terrain = match.plains
        center = grid[6][6]
        center.terrain = match.mountain

        with patch.object(generator.rng, "randint", return_value=1):
            generator._mountain_edge_forests(grid, match.mountain, match.forest)

        self.assertIs(center.terrain, match.mountain)
        self.assertTrue(any(neighbor.terrain is match.forest for neighbor in center.nList))

    def test_mountain_peaks_and_ridges_have_doubled_variable_shapes(self):
        match = MatchInfo(30, 9, [], "")
        generator = MapGenerator(30, random.Random(0))
        grid = generator.build(match)
        peak = [15, 15]

        generator._place_mountain_peak(grid, peak, match.mountain, width=6)
        self.assertTrue(all(
            grid[y][x].terrain is match.mountain
            for y in range(12, 18) for x in range(12, 18)
        ))

        generator._place_mountain_peak(grid, peak, match.mountain, width=10)
        self.assertTrue(all(
            grid[y][x].terrain is match.mountain
            for y in range(10, 20) for x in range(10, 20)
        ))

        generator._draw_mountain_ridge(grid, [6, 15], [24, 15], match.mountain, width=4)
        self.assertTrue(all(
            grid[y][15].terrain is match.mountain for y in range(13, 17)
        ))

        generator._draw_mountain_ridge(grid, [6, 15], [24, 15], match.mountain, width=20)
        self.assertTrue(all(
            grid[y][15].terrain is match.mountain for y in range(5, 25)
        ))

    def test_large_mountain_ridges_extend_six_to_thirty_two_tiles_when_space_allows(self):
        generator = MapGenerator(100, random.Random(0))
        peak = [50, 50]
        endpoint = generator._ridge_endpoint(peak)

        self.assertIsNotNone(endpoint)
        self.assertGreaterEqual(math.dist(peak, endpoint), 6)
        self.assertLessEqual(math.dist(peak, endpoint), 32)

    def test_mountain_ranges_always_draw_a_ridge_narrower_than_its_length(self):
        match = MatchInfo(100, 9, [], "")
        generator = MapGenerator(100, random.Random(0))
        grid = generator.build(match)

        def valid_endpoint(peak):
            direction = -10 if peak[0] > 20 else 10
            return [peak[0] + direction, peak[1]]

        with patch.object(generator, "_ridge_endpoint", side_effect=valid_endpoint), patch.object(
            generator, "_draw_mountain_ridge",
        ) as draw_ridge:
            generator._mountain_ranges(grid, match.mountain)

        self.assertGreaterEqual(draw_ridge.call_count, 1)
        for call in draw_ridge.call_args_list:
            _, start, end, _, width = call.args
            self.assertLess(width, math.dist(start, end))

    def test_roads_can_carve_a_pass_through_mountains(self):
        match = MatchInfo(12, 9, [], "")
        generator = MapGenerator(12, random.Random(0))
        grid = generator.build(match)
        grid[4][4].terrain = match.mountain

        generator._draw_road(grid, [3, 4], [5, 4], match.road)

        self.assertIs(grid[4][4].terrain, match.road)

    def test_roads_cross_water_as_bridges(self):
        match = MatchInfo(12, 9, [], "")
        generator = MapGenerator(12, random.Random(0))
        grid = generator.build(match)
        grid[4][4].terrain = match.water

        generator._draw_road(grid, [3, 4], [5, 4], match.road)

        self.assertIs(grid[4][4].terrain, match.road)

    def test_roads_connect_opposite_playable_map_edges(self):
        match = MatchInfo(12, 9, [], "")
        generator = MapGenerator(12, random.Random(0))
        grid = generator.build(match)
        for row in grid[1:-1]:
            for cell in row[1:-1]:
                cell.terrain = match.plains

        generator._roads(grid, match.road, "Light")

        reaches_left_and_right = (
            any(grid[y][1].terrain is match.road for y in range(1, generator.height - 1))
            and any(
                grid[y][generator.width - 2].terrain is match.road
                for y in range(1, generator.height - 1)
            )
        )
        reaches_top_and_bottom = (
            any(grid[1][x].terrain is match.road for x in range(1, generator.width - 1))
            and any(
                grid[generator.height - 2][x].terrain is match.road
                for x in range(1, generator.width - 1)
            )
        )
        self.assertTrue(reaches_left_and_right or reaches_top_and_bottom)

    def test_highway_has_two_parallel_road_lanes(self):
        match = MatchInfo(30, 9, [], "")
        generator = MapGenerator(30, random.Random(0))
        grid = generator.build(match)
        for row in grid[1:-1]:
            for cell in row[1:-1]:
                cell.terrain = match.plains

        endpoints = ([1, 15], [28, 15])
        with patch.object(generator, "_road_endpoints", return_value=endpoints):
            generator._highways(grid, match.road, count=1)

        self.assertTrue(all(
            grid[y][x].terrain is match.road
            for y in (15, 16) for x in range(1, 29)
        ))

    def test_mountain_road_passes_can_make_single_and_two_lane_tunnels(self):
        match = MatchInfo(12, 9, [], "")
        generator = MapGenerator(12, random.Random(0))
        grid = generator.build(match)
        # A road directly between mountain walls becomes a single-lane tunnel.
        grid[5][5].terrain = match.road
        grid[5][4].terrain = match.mountain
        grid[5][6].terrain = match.mountain
        # A mountain beside a two-lane road converts both road tiles.
        grid[7][5].terrain = match.mountain
        grid[7][6].terrain = match.road
        grid[7][7].terrain = match.road

        with patch.object(generator.rng, "randint", return_value=1):
            generator._tunnel_passes(grid, match.road, match.mountain, match.tunnel)

        self.assertIs(grid[5][5].terrain, match.tunnel)
        self.assertIs(grid[7][6].terrain, match.tunnel)
        self.assertIs(grid[7][7].terrain, match.tunnel)
        self.assertEqual(match.tunnel.moveCost, [0, 0, 0, 0, 2, 2, 2])

    def test_mountains_buff_medium_shooters_and_cover_small_targets(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        shooter = match.teamList[1].squadsList[0].mechList[1]  # Kestrel, size 3.
        target = match.pov  # Pathfinder Lancer, size 2.
        weapon = shooter.mechClass.gunList[0]
        shooter.pos = [4, 4]
        target.pos = [10, 4]
        match.map[4][4].terrain = match.plains
        match.map[4][10].terrain = match.plains

        baseline = weapon.effective_accuracy(match, shooter, target)

        match.map[4][4].terrain = match.mountain
        self.assertAlmostEqual(
            weapon.effective_accuracy(match, shooter, target), baseline * 1.15,
        )

        match.map[4][4].terrain = match.plains
        match.map[4][10].terrain = match.forest
        self.assertAlmostEqual(
            weapon.effective_accuracy(match, shooter, target), baseline * 0.85,
        )

    def test_optional_terrain_defaults_on_and_can_be_disabled(self):
        self.assertTrue(all(DEFAULT_TERRAIN_ENABLED.values()))

        match = MatchInfo(20, 9, [], "")
        match.map = MapGenerator(20, random.Random(0)).build(match)
        self.assertTrue(any(cell.terrain is match.water for row in match.map for cell in row))

        disabled = MatchInfo(20, 9, [], "")
        disabled.map = MapGenerator(
            20, random.Random(0),
            terrain_enabled={terrain: False for terrain in DEFAULT_TERRAIN_ENABLED},
        ).build(disabled)
        self.assertTrue(all(cell.terrain in (disabled.border, disabled.plains) for row in disabled.map for cell in row))

    def test_game_creates_a_small_match(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()

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
        first = Game(map_size=40, window_size=9, rng=random.Random(7)).create_match()
        second = Game(map_size=40, window_size=9, rng=random.Random(7)).create_match()

        first_terrain = [[cell.terrain.name for cell in row] for row in first.map]
        second_terrain = [[cell.terrain.name for cell in row] for row in second.map]

        self.assertEqual(first_terrain, second_terrain)
        self.assertEqual(
            [mech.pos for mech in first.entities],
            [mech.pos for mech in second.entities],
        )

    def test_squad_roster_lists_pilots_mechs_and_positions(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()

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

        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
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
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        lancer = match.pov
        dash = lancer.mechClass.hull.abilities[0]
        lancer.pos = [4, 4]
        for other in match.entities:
            if other is not lancer:
                other.pos = [15, 15]
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
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        lancer = match.teamList[0].squadsList[0].mechList[1]
        lancer.pos = [4, 4]
        dash = lancer.mechClass.hull.abilities[0]
        lance = next(weapon for weapon in lancer.mechClass.gunList if weapon.isMelee)

        self.assertTrue(dash.use(match, lancer, "d"))
        self.assertEqual(lance.dmg, 21)

        lancer.clearTurnAbilities()
        self.assertEqual(lance.dmg, 18)

    def test_kestrel_sensor_overdrive_boosts_and_then_clears_sensors(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
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
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
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
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()

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
