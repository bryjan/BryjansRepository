"""Move orders route an actual sensor/mortar squad around rivers to bridges."""

import random
import unittest
from unittest.mock import patch

from mechgame.ai import execute_squad_movement
from mechgame.catalog import create_mech
from mechgame.entities import Entity, Pilot
from mechgame.formation import destination_route, formation_area
from mechgame.runner import Game
from mechgame.squad_orders import issue
from mechgame.teams import Squad, Team


class MoveRouteTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, rng=random.Random(0)).create_match()
        self.squad = Squad("Mortar support", [
            Entity(create_mech("lancer.pathfinder"), Pilot("Sensor")),
            Entity(create_mech("lancer.mortar"), Pilot("Arc")),
            Entity(create_mech("lancer.mortar"), Pilot("Fuse")),
        ], "support", playerControlled=True)
        team = Team("Player", [self.squad])
        team.mapVisibility.show_all_terrain = True
        self.match.teamList[0] = team
        self.squad.playerControlled = False
        self.match.entities = list(self.squad.mechList)
        self.match.pov = self.squad.squadLead
        for row in self.match.map[1:-1]:
            for cell in row[1:-1]:
                cell.terrain = self.match.plains
        for y in range(1, 39):
            self.match.map[y][20].terrain = self.match.water
        self.match.map[5][20].terrain = self.match.road
        for mech, position in zip(self.squad.mechList, ([18, 20], [15, 20], [15, 23])):
            mech.pos = list(position)
        issue(self.match, self.squad, "move", (26, 20))

    def test_move_route_initially_moves_away_from_destination_to_find_bridge(self):
        leader = self.squad.squadLead
        route = destination_route(self.match, leader, (26, 20), 6)
        self.assertIn([20, 5], route)
        self.assertTrue(any(point[1] < 20 for point in route))
        self.assertTrue(all(not self.match.map[y][x].terrain.requireFloat for x, y in route))

    def test_whole_squad_crosses_bridge_under_move_order(self):
        with patch("builtins.print"):
            for turn in range(45):
                self.match.matchRound = turn
                self.squad.roundRefresh(self.match)
                execute_squad_movement(self.match, self.squad)
                if all(mech.pos[0] > 20 for mech in self.squad.mechList):
                    break
        self.assertTrue(all(mech.pos[0] > 20 for mech in self.squad.mechList),
                        [mech.pos for mech in self.squad.mechList])
        self.assertTrue(all(mech.energy >= mech.mechClass.energyMax * .7 for mech in self.squad.mechList))

    def test_opposite_bank_is_not_in_formation_even_when_physically_close(self):
        leader, follower, _ = self.squad.mechList
        leader.pos, follower.pos = [23, 20], [19, 20]
        self.assertNotIn(tuple(follower.pos), formation_area(self.match, follower, 10))
        self.assertIn((24, 20), formation_area(self.match, follower, 10))

    def test_no_bridge_does_not_allow_a_phantom_water_crossing(self):
        self.match.map[5][20].terrain = self.match.water
        self.assertEqual(destination_route(self.match, self.squad.squadLead, (26, 20), 6), [])
