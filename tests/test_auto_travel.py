"""Automatic following works for a whole column and routes around obstacles."""

import random
import math
import unittest
from unittest.mock import patch

from mechgame.runner import Game
from mechgame.formation import formation_radius


class AutoTravelTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, rng=random.Random(0)).create_match()
        self.squad = self.match.playerSquad
        self.leader = self.squad.squadLead
        self.match.entities = list(self.squad.mechList)
        self.squad.team.mapVisibility.show_all_terrain = True
        self.squad.autoTravelEnabled = True
        for row in self.match.map[1:-1]:
            for cell in row[1:-1]:
                cell.terrain = self.match.plains

    def test_every_follower_in_a_road_column_advances_regardless_of_roster_order(self):
        for x in range(2, 35):
            self.match.map[10][x].terrain = self.match.road
        self.leader.pos = [25, 10]
        followers = self.squad.mechList[1:]
        for index, mech in enumerate(followers):
            mech.pos = [3 + index, 10]
        starts = {mech: list(mech.pos) for mech in followers}
        with patch("builtins.print"):
            self.assertTrue(self.leader.moveTo(self.match, [26, 10]))
        for mech in followers:
            self.assertGreater(mech.pos[0], starts[mech][0])
            self.assertEqual(mech.pos[1], 10)
            self.assertLess(mech.ap, mech.mechClass.apMax)
        self.assertEqual(len({tuple(mech.pos) for mech in self.match.entities}), len(self.match.entities))
        self.assertFalse(self.match.turnEnded)

    def test_followers_catch_up_before_reaching_full_visual_range(self):
        follower = self.squad.mechList[1]
        self.squad.mechList = [self.leader, follower]
        self.match.entities = list(self.squad.mechList)
        self.leader.pos = [20, 10]
        self.leader.visPower = 14
        follower.pos = [8, 10]
        self.assertEqual(formation_radius(self.leader), 10)
        self.assertTrue(self.leader.moveTo(self.match, [21, 10]))
        self.assertGreater(follower.pos[0], 8)
        # A distant follower can spend all six movement points before it
        # reaches five tiles; it must still make progress within its budget.
        self.assertLessEqual(math.dist(follower.pos, self.leader.pos), 10)

    def test_fixed_leader_tether_does_not_expand_with_sensor_power(self):
        self.leader.visPower = 40
        self.assertEqual(formation_radius(self.leader), 10)

    def test_isolated_follower_closes_teammate_gap_inside_leader_tether(self):
        follower = self.squad.mechList[1]
        self.squad.mechList = [self.leader, follower]
        self.match.entities = list(self.squad.mechList)
        self.leader.pos = [20, 10]
        follower.pos = [12, 10]
        with patch("builtins.print"):
            self.leader.moveTo(self.match, [21, 10])
        self.assertLessEqual(math.dist(follower.pos, self.leader.pos), 5)

    def test_units_in_formation_hold_and_exhausted_units_do_not_move(self):
        followers = self.squad.mechList[1:]
        self.leader.pos = [20, 20]
        for mech, position in zip(followers, ([17, 17], [17, 23], [23, 17], [3, 20])):
            mech.pos = list(position)
        followers[-1].ap = 0
        starts = [list(mech.pos) for mech in followers]
        with patch("builtins.print"):
            self.leader.moveTo(self.match, [21, 20])
        self.assertEqual([mech.pos for mech in followers], starts)

    def test_offroad_follower_detours_to_road_instead_of_stopping_at_wall(self):
        follower = self.squad.mechList[1]
        self.squad.mechList = [self.leader, follower]
        self.match.entities = list(self.squad.mechList)
        for x in range(10, 35):
            self.match.map[10][x].terrain = self.match.road
        # The only way around this wall initially leads away from the road.
        for y in range(4, 17):
            self.match.map[y][5].terrain = self.match.blank
        self.leader.pos = [20, 10]
        follower.pos = [4, 10]
        with patch("builtins.print"):
            for turn in range(5):
                for mech in self.squad.mechList:
                    mech.roundRefresh(self.match)
                    mech.energy = mech.mechClass.energyMax
                self.assertTrue(self.leader.moveTo(self.match, [21 + turn, 10]))
        self.assertGreater(follower.pos[0], 5)
        self.assertIs(self.match.map[follower.pos[1]][follower.pos[0]].terrain, self.match.road)


if __name__ == "__main__":
    unittest.main()
