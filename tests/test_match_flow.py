import random
import unittest
from unittest.mock import patch

from mechgame.catalog import create_mech
from mechgame.entities import Entity, Pilot
from mechgame.runner import Game
from mechgame.teams import Squad, Team


class MatchFlowTests(unittest.TestCase):
    def test_demo_match_can_advance_between_teams_and_rounds(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        player_team = match.pov.team

        match.nextSquadTurn()
        self.assertIsNot(match.pov.team, player_team)
        self.assertFalse(match.advTurn)

        match.nextSquadTurn()
        self.assertIs(match.pov.team, player_team)
        self.assertEqual(match.matchRound, 1)

    def test_actions_do_not_change_squads_without_an_end_request(self):
        game = Game(map_size=40, window_size=9, rng=random.Random(0))
        match = game.create_match()
        active_mech = match.pov

        match.advTurn = True
        game.advance_turn_if_requested(match)
        self.assertIs(match.pov, active_mech)

        match.turnEnded = True
        game.advance_turn_if_requested(match)
        self.assertIsNot(match.pov, active_mech)

    def test_match_assigns_default_elimination_goals_to_teams(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()

        for team in match.teamList:
            self.assertEqual(team.currentGoal.kind, "eliminate_enemies")
            self.assertEqual(team.currentGoal.priority, 1)
            self.assertEqual(team.goalHistory, [team.currentGoal])

    def test_match_goals_prefer_declared_scenario_objectives(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        match.mapFeatures.add_objective("relay", "Relay Station", "capture", [(12, 12)])

        match.assignTeamGoals()

        for team in match.teamList:
            self.assertEqual(team.currentGoal.kind, "secure_objective")
            self.assertEqual(team.currentGoal.objective_id, "relay")
            self.assertEqual(team.currentGoal.target_tiles, ((12, 12),))

    def test_match_can_issue_multiple_role_aware_team_objectives(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        team = match.teamList[1]
        patrol = match.issueTeamObjective(
            team, "patrol", 40, [(4, 6), (8, 6)],
            "Patrol the western road.", required_roles=["sensor", "skirmisher"],
        )
        defense = match.issueTeamObjective(
            team, "defend", 80, [(12, 12)],
            "Hold the relay station.", required_roles=["front_line"],
        )

        self.assertIs(team.currentGoal, defense)
        self.assertEqual(team.currentGoals, [defense, patrol, team.goalHistory[0]])
        self.assertEqual(patrol.locations, ((4, 6), (8, 6)))
        self.assertEqual(patrol.message, "Patrol the western road.")
        self.assertEqual(patrol.required_roles, ("sensor", "skirmisher"))

    def test_destroyed_squad_is_skipped_in_turn_order(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        reserve_mech = Entity(create_mech("lancer.type_a"), Pilot("Reserve"))
        reserve_mech.pos = [4, 4]
        reserve_team = Team(
            "Reserve Team",
            [Squad("Reserve Squad", [reserve_mech], "Combat")],
        )
        match.teamList.append(reserve_team)
        match.entities.append(reserve_mech)

        for enemy in list(match.teamList[1].squadsList[0].mechList):
            enemy.destroy(match)

        self.assertTrue(match.nextSquadTurn())
        self.assertIs(match.pov, reserve_mech)
        self.assertEqual(match.matchRound, 0)

    def test_last_operational_team_wins_instead_of_crashing_turn_order(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        player_team = match.pov.team

        for enemy in list(match.teamList[1].squadsList[0].mechList):
            enemy.destroy(match)

        self.assertFalse(match.nextSquadTurn())
        self.assertTrue(match.matchOver)
        self.assertIs(match.winner, player_team)
        self.assertIn("wins", match.resultMessage)

    def test_round_effects_reselect_when_the_next_squad_is_destroyed(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        reserve_mech = Entity(create_mech("lancer.type_a"), Pilot("Reserve"))
        reserve_mech.pos = [4, 4]
        reserve_team = Team(
            "Reserve Team",
            [Squad("Reserve Squad", [reserve_mech], "Combat")],
        )
        match.teamList.append(reserve_team)
        match.entities.append(reserve_mech)
        match.pov = reserve_mech

        player_squad = match.teamList[0].squadsList[0]

        def destroy_player_squad(_):
            for mech in list(player_squad.mechList):
                mech.destroy(match)

        with patch("mechgame.match.effects.advance_effects", side_effect=destroy_player_squad):
            self.assertTrue(match.nextSquadTurn())

        self.assertIs(match.pov.team, match.teamList[1])
        self.assertEqual(match.matchRound, 1)
