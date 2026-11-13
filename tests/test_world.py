import random
import unittest

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

        self.assertEqual(len(match.entities), 7)
        self.assertEqual(match.pov.pilot.name, "B")

        self.assertEqual(
            [mech.mechClass.name for mech in match.teamList[0].squadsList[0].mechList],
            [
                "Lancer Type.S Pathfinder",
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

    def test_bastion_heavy_beam_accuracy_is_reduced(self):
        bastion = create_mech("bastion")
        beam = next(weapon for weapon in bastion.gunList if weapon.name == "Heavy Melting Beam")

        self.assertEqual(beam.accuracy, 27)
