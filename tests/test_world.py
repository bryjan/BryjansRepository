import random
import unittest

from mechgame.match import MatchInfo
from mechgame.runner import Game
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

        self.assertEqual(len(match.entities), 6)
        self.assertEqual(match.pov.pilot.name, "B")
