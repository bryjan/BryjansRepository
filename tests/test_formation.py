"""Followers keep their movement burst and route around known obstructions."""

import math
import random
import unittest

from mechgame.runner import Game
from mechgame.ai import _can_begin_movement, _move_follower


class FormationTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        self.squad = self.match.playerSquad
        self.leader, self.follower = self.squad.mechList[:2]
        self.squad.mechList = [self.leader, self.follower]
        self.match.entities = [self.leader, self.follower]
        self.squad.team.mapVisibility.show_all_terrain = True
        for row in self.match.map:
            for cell in row:
                if cell.terrain is not self.match.border:
                    cell.terrain = self.match.plains
        self.squad.setMovementPolicy(mode="move")

    def test_repeated_follow_passes_do_not_restart_the_energy_gate(self):
        follower = self.follower
        follower.pos = [5, 10]
        starting_ap, starting_energy = follower.ap, follower.energy
        for _ in range(4):
            self.leader.pos = [follower.pos[0] + 11, 10]
            self.assertTrue(_move_follower(self.match, self.squad, follower, 10, False))
            self.assertLessEqual(math.dist(follower.pos, self.leader.pos), 10)
        self.assertEqual(follower.ap, starting_ap - 4)
        self.assertEqual(follower.energy, starting_energy - 4)
        self.assertTrue(_can_begin_movement(follower, "move"))

    def test_new_turn_requires_a_new_burst_ceiling(self):
        follower = self.follower
        follower.pos = [5, 10]
        self.leader.pos = [16, 10]
        _move_follower(self.match, self.squad, follower, 10, False)
        follower.energy = math.ceil(follower.mechClass.energyMax * .7)
        follower.roundRefresh(self.match)
        self.assertIsNone(follower.movementBurstMode)
        self.assertFalse(_can_begin_movement(follower, "move"))

    def test_follower_detours_around_wall_instead_of_oscillating(self):
        follower = self.follower
        follower.pos = [4, 10]
        self.leader.pos = [22, 10]
        for y in range(4, 17):
            self.match.map[y][5].terrain = self.match.blank
        for _ in range(5):
            follower.ap = follower.mechClass.apMax
            follower.mp = follower.mechClass.mpMax
            follower.energy = follower.mechClass.energyMax
            _move_follower(self.match, self.squad, follower, 10, False)
            if math.dist(follower.pos, self.leader.pos) <= 10:
                break
        self.assertGreater(follower.pos[0], 5)
        self.assertLessEqual(math.dist(follower.pos, self.leader.pos), 10)


if __name__ == "__main__":
    unittest.main()
