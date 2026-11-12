import random
import unittest

from mechgame.runner import Game


class MatchFlowTests(unittest.TestCase):
    def test_demo_match_can_advance_between_teams_and_rounds(self):
        match = Game(map_size=20, window_size=9, rng=random.Random(0)).create_match()
        player_team = match.pov.team

        match.nextSquadTurn()
        self.assertIsNot(match.pov.team, player_team)
        self.assertFalse(match.advTurn)

        match.nextSquadTurn()
        self.assertIs(match.pov.team, player_team)
        self.assertEqual(match.matchRound, 1)

    def test_actions_do_not_change_squads_without_an_end_request(self):
        game = Game(map_size=20, window_size=9, rng=random.Random(0))
        match = game.create_match()
        active_mech = match.pov

        match.advTurn = True
        game.advance_turn_if_requested(match)
        self.assertIs(match.pov, active_mech)

        match.turnEnded = True
        game.advance_turn_if_requested(match)
        self.assertIsNot(match.pov, active_mech)
