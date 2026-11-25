"""Patrol walks use adjacent road cells, including stamped and broken roads."""

import unittest

from mechgame.patrols import connected_walk
from mechgame.stamps import CityBlockStamp


class PatrolRouteTests(unittest.TestCase):
    def assert_walkable(self, route):
        self.assertGreater(len(route), 1)
        for first, second in zip(route, route[1:]):
            self.assertEqual(max(abs(first[0] - second[0]), abs(first[1] - second[1])), 1)

    def test_ordered_road_keeps_its_original_path(self):
        road = tuple((x, 10) for x in range(2, 30))
        self.assertEqual(connected_walk(road, (10, 10)), road)

    def test_stamp_perimeter_becomes_a_continuous_repeatable_walk(self):
        footprint = CityBlockStamp(10, 10).boundary_positions((10, 10))
        route = connected_walk(footprint, (10, 10))
        self.assert_walkable(route)
        self.assertEqual(set(route), set(footprint))
        self.assertEqual(route[0], route[-1])

    def test_gap_splits_a_recorded_road_instead_of_creating_a_distant_waypoint(self):
        road = [(10, y) for y in range(1, 10)] + [(10, y) for y in range(20, 30)]
        route = connected_walk(road, (10, 9))
        self.assert_walkable(route)
        self.assertEqual(route[-1], (10, 9))
        self.assertTrue(all(y < 10 for _, y in route))
        self.assertEqual(connected_walk(road, (10, 29))[0], (10, 20))

    def test_highway_lane_order_has_no_jump_between_lane_ends(self):
        footprint = [(x, 10) for x in range(2, 30)] + [(x, 11) for x in range(2, 30)]
        route = connected_walk(footprint)
        self.assert_walkable(route)
        self.assertEqual(set(route), set(footprint))


if __name__ == "__main__":
    unittest.main()
