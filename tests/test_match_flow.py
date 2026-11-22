import math
import random
import unittest
from unittest.mock import patch

from mechgame.ai import execute_squad_movement
from mechgame.catalog import create_mech
from mechgame.entities import Entity, Pilot
from mechgame.missions import MissionGenerator
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

        player_squad = match.teamList[0].squadsList[0]
        enemy_squad = match.teamList[1].squadsList[0]
        self.assertIsNone(player_squad.currentGoal)
        self.assertEqual(enemy_squad.currentGoal.kind, "eliminate_enemies")
        self.assertEqual(enemy_squad.currentGoal.team_goal_id, "eliminate_enemies")

    def test_squad_combat_force_weights_ready_mechs_by_size_class(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        player_squad = match.teamList[0].squadsList[0]
        enemy_squad = match.teamList[1].squadsList[0]

        player_squad.refreshCombatForce()
        enemy_squad.refreshCombatForce()

        self.assertEqual(player_squad.combatReadyCount, 5)
        self.assertEqual(player_squad.combatForce, 6.4)
        self.assertEqual(enemy_squad.combatReadyCount, 3)
        self.assertEqual(enemy_squad.combatForce, 10.2)

        player_squad.mechList[0].combatReady = False
        player_squad.refreshCombatForce()
        self.assertEqual(player_squad.combatForce, 5.5)

    def test_squad_operational_flags_track_capabilities_and_combat_effectiveness(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        player_squad = match.teamList[0].squadsList[0]

        self.assertTrue(player_squad.roleCapabilityFlags["sensor"])
        self.assertTrue(player_squad.roleCapabilityFlags["artillery"])
        self.assertTrue(player_squad.combatEffective)
        self.assertFalse(player_squad.shouldLeaveBattlefield)
        self.assertEqual(player_squad.combatEffectiveness, 100)

        for mech in player_squad.mechList:
            mech.combatReady = False
        player_squad.refreshCombatForce()

        self.assertEqual(player_squad.combatForce, 0)
        self.assertEqual(player_squad.combatEffectiveness, 0)
        self.assertFalse(player_squad.combatEffective)
        self.assertTrue(player_squad.shouldLeaveBattlefield)

    def test_non_attacking_roles_reduce_force_while_combat_specialists_gain_bonus(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        pathfinder = match.teamList[0].squadsList[0].mechList[0]
        standard_lancer = match.teamList[0].squadsList[0].mechList[1]

        self.assertEqual(pathfinder.mechClass.nonAttackingRoles, ["sensor", "scout"])
        self.assertEqual(pathfinder.mechClass.combatForceMultiplier, 0.9)
        self.assertIn("anti_heavy", standard_lancer.mechClass.roles)
        self.assertEqual(standard_lancer.mechClass.combatForceMultiplier, 1.4)

        bastion = match.teamList[1].squadsList[0].mechList[0]
        self.assertIn("anti_swarm", bastion.mechClass.roles)
        self.assertIn("sustain", bastion.mechClass.roles)
        self.assertEqual(bastion.mechClass.combatForceMultiplier, 1.2)

        mortar = match.teamList[0].squadsList[0].mechList[-1]
        self.assertTrue(mortar.mechClass.hasLongRangeFireSupport)
        self.assertIn("long_range_fire_support", mortar.mechClass.roles)
        self.assertEqual(mortar.mechClass.combatForceMultiplier, 1.3)

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
        enemy_squad = team.squadsList[0]
        self.assertEqual(enemy_squad.currentGoal.kind, "defend")
        self.assertTrue(enemy_squad.canFulfillCurrentGoal)
        self.assertEqual(
            [goal.kind for goal in enemy_squad.currentGoals],
            ["defend", "patrol", "eliminate_enemies"],
        )
        self.assertGreaterEqual(enemy_squad.roleReadiness()["front_line"], 60)

    def test_goal_assignment_normalizes_a_single_coordinate_and_skips_empty_squads(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        team = match.teamList[1]
        empty_squad = Squad("Empty Reserve", [], "Combat")
        empty_squad.team = team
        team.squadsList.insert(0, empty_squad)

        goal = match.issueTeamObjective(team, "defend", 80, (12, 12), "Hold position.")

        self.assertEqual(goal.locations, ((12, 12),))
        self.assertIsNone(empty_squad.currentGoal)
        self.assertIsNotNone(team.squadsList[1].currentGoal)

    def test_destroying_a_squad_leader_promotes_the_next_operational_mech(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        squad = match.pov.squad
        original_leader = squad.squadLead

        original_leader.destroy(match)

        self.assertNotIn(original_leader, squad.mechList)
        self.assertIs(squad.squadLead, squad.mechList[0])

    def test_ai_squad_leader_advances_then_followers_hold_valid_formation(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        enemy_team = match.teamList[1]
        squad = enemy_team.squadsList[0]
        for row in match.map:
            for cell in row:
                cell.terrain = match.plains
        for index, entity in enumerate(match.teamList[0].squadsList[0].mechList):
            entity.pos = [30 + (index % 2), 30 + (index // 2)]

        leader, first_follower, second_follower = squad.mechList
        leader.pos = [10, 10]
        first_follower.pos = [7, 10]
        second_follower.pos = [7, 13]
        match.issueTeamObjective(enemy_team, "defend", 80, (20, 10), "Hold position.")

        moved = execute_squad_movement(match, squad)

        self.assertLess(leader.pos[0], 20)
        self.assertTrue(all(mech is leader for mech in moved))
        self.assertLessEqual(((first_follower.pos[0] - leader.pos[0]) ** 2 + (first_follower.pos[1] - leader.pos[1]) ** 2) ** .5, 10)
        self.assertLessEqual(((second_follower.pos[0] - leader.pos[0]) ** 2 + (second_follower.pos[1] - leader.pos[1]) ** 2) ** .5, 10)
        self.assertLess(leader.ap, leader.mechClass.apMax)

    def test_ai_elimination_squad_searches_toward_map_center_without_a_contact(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        squad = match.teamList[1].squadsList[0]
        leader = squad.squadLead
        for row in match.map:
            for cell in row:
                cell.terrain = match.plains
        leader.pos = [30, 30]
        for index, follower in enumerate(squad.mechList[1:], start=1):
            follower.pos = [30 - index * 3, 30]
        for index, entity in enumerate(match.teamList[0].squadsList[0].mechList):
            entity.pos = [35 + (index % 2), 35 + (index // 2)]
        leader.directlyVisibleEnemies = []
        leader.trackedEnemies = []

        execute_squad_movement(match, squad)

        self.assertLess(((leader.pos[0] - 20) ** 2 + (leader.pos[1] - 20) ** 2) ** .5, 14.2)

    def test_ai_movement_modes_preserve_their_configured_energy_reserves(self):
        for mode, reserve in (("patrol", None), ("move", .70), ("double_time", .20)):
            with self.subTest(mode=mode):
                match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
                squad = match.teamList[1].squadsList[0]
                leader = squad.squadLead
                for row in match.map:
                    for cell in row:
                        cell.terrain = match.plains
                for index, entity in enumerate(match.teamList[0].squadsList[0].mechList):
                    entity.pos = [35 + (index % 2), 35 + (index // 2)]
                leader.pos = [10, 10]
                for index, follower in enumerate(squad.mechList[1:], start=1):
                    follower.pos = [7, 10 + index * 3]
                match.issueTeamObjective(match.teamList[1], "defend", 80, (30, 10), "Advance.")
                squad.setMovementPolicy(mode=mode)
                starting_energy = leader.energy

                execute_squad_movement(match, squad)

                spent = starting_energy - leader.energy
                if reserve is None:
                    self.assertLessEqual(spent, leader.mechClass.energyGen)
                else:
                    self.assertGreaterEqual(leader.energy, math.ceil(leader.mechClass.energyMax * reserve))

    def test_ai_leader_holds_position_when_a_follower_needs_to_regroup(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        squad = match.teamList[1].squadsList[0]
        leader, first_follower, second_follower = squad.mechList
        for row in match.map:
            for cell in row:
                cell.terrain = match.plains
        for index, entity in enumerate(match.teamList[0].squadsList[0].mechList):
            entity.pos = [35 + (index % 2), 35 + (index // 2)]
        leader.pos = [10, 10]
        first_follower.pos = [26, 10]
        second_follower.pos = [7, 13]
        match.issueTeamObjective(match.teamList[1], "defend", 80, (30, 10), "Advance.")

        moved = execute_squad_movement(match, squad)

        self.assertEqual(leader.pos, [10, 10])
        self.assertNotIn(leader, moved)
        self.assertLess(first_follower.pos[0], 26)

    def test_ai_followers_inside_leader_tether_do_not_reposition(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        squad = match.teamList[1].squadsList[0]
        leader, first_follower, second_follower = squad.mechList
        for row in match.map:
            for cell in row:
                cell.terrain = match.plains
        for index, entity in enumerate(match.teamList[0].squadsList[0].mechList):
            entity.pos = [35 + (index % 2), 35 + (index // 2)]
        leader.pos = [10, 10]
        # The followers are closer together than the former spacing preference,
        # but both are safely inside the leader's formation tether.
        first_follower.pos = [8, 10]
        second_follower.pos = [8, 11]
        match.issueTeamObjective(match.teamList[1], "defend", 80, (30, 10), "Advance.")

        moved = execute_squad_movement(match, squad)

        self.assertTrue(moved)
        self.assertTrue(all(mech is leader for mech in moved))
        self.assertEqual(first_follower.pos, [8, 10])
        self.assertEqual(second_follower.pos, [8, 11])

    def test_ai_leader_waits_after_regroup_for_reserves_to_recover(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        squad = match.teamList[1].squadsList[0]
        leader, first_follower, second_follower = squad.mechList
        for row in match.map:
            for cell in row:
                cell.terrain = match.plains
        for index, entity in enumerate(match.teamList[0].squadsList[0].mechList):
            entity.pos = [35 + (index % 2), 35 + (index // 2)]
        leader.pos = [10, 10]
        first_follower.pos = [26, 10]
        second_follower.pos = [7, 13]
        match.issueTeamObjective(match.teamList[1], "defend", 80, (30, 10), "Advance.")
        first_follower.energy = math.ceil(first_follower.mechClass.energyMax * .90)

        execute_squad_movement(match, squad)
        self.assertLessEqual(
            math.dist(first_follower.pos, leader.pos), max(10, leader.visPower),
        )
        self.assertLess(first_follower.energy, math.ceil(first_follower.mechClass.energyMax * .90))

        moved = execute_squad_movement(match, squad)
        self.assertEqual(leader.pos, [10, 10])
        self.assertNotIn(leader, moved)

        first_follower.energy = math.ceil(first_follower.mechClass.energyMax * .90)
        moved = execute_squad_movement(match, squad)
        self.assertIn(leader, moved)

    def test_ai_regroup_waits_for_follower_to_reach_its_movement_ceiling(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        squad = match.teamList[1].squadsList[0]
        leader, first_follower, second_follower = squad.mechList
        for row in match.map:
            for cell in row:
                cell.terrain = match.plains
        for index, entity in enumerate(match.teamList[0].squadsList[0].mechList):
            entity.pos = [35 + (index % 2), 35 + (index // 2)]
        leader.pos = [10, 10]
        first_follower.pos = [26, 10]
        second_follower.pos = [7, 13]
        match.issueTeamObjective(match.teamList[1], "defend", 80, (30, 10), "Advance.")
        first_follower.energy = math.ceil(first_follower.mechClass.energyMax * .90) - 1

        moved = execute_squad_movement(match, squad)

        self.assertEqual(leader.pos, [10, 10])
        self.assertNotIn(first_follower, moved)
        first_follower.energy = math.ceil(first_follower.mechClass.energyMax * .90)
        moved = execute_squad_movement(match, squad)
        self.assertIn(first_follower, moved)

    def test_road_patrol_moves_a_column_on_roads_without_spacing_requirement(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        squad = match.teamList[1].squadsList[0]
        leader, first_follower, second_follower = squad.mechList
        for row in match.map:
            for cell in row:
                cell.terrain = match.plains
        for index, entity in enumerate(match.teamList[0].squadsList[0].mechList):
            entity.pos = [35 + (index % 2), 35 + (index // 2)]
        for x in range(1, match.mapWidth - 1):
            match.map[10][x].terrain = match.road
        leader.pos = [10, 10]
        first_follower.pos = [1, 10]
        second_follower.pos = [4, 10]
        match.issueTeamObjective(match.teamList[1], "patrol_map", 80, (30, 10), "Patrol road.")

        moved = execute_squad_movement(match, squad)

        self.assertTrue(moved)
        self.assertTrue(all(match.map[mech.pos[1]][mech.pos[0]].terrain is match.road for mech in squad.mechList))

    def test_mission_generator_creates_initial_mission_templates(self):
        match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        missions = MissionGenerator(match)
        player, enemy = match.teamList

        recovery = missions.add_pilot_recovery(player, (8, 8), "Downed Scout")
        mech_recovery = missions.add_recover_or_steal_mech(player, (10, 8), "Warden")
        attack = missions.add_attack_military_base(enemy)
        patrol = missions.add_map_patrol(enemy)
        local_patrol = missions.add_patrol_near_location(enemy, (12, 12))
        defense = missions.add_defend_location(player, (14, 14))

        self.assertEqual(recovery.kind, "pilot_recovery")
        self.assertEqual(recovery.required_roles, ("sensor", "scout"))
        self.assertEqual(mech_recovery.kind, "recover_or_steal_mech")
        self.assertEqual(mech_recovery.required_roles, ("front_line", "skirmisher"))
        self.assertTrue(attack.locations)
        self.assertTrue(match.mapFeatures.military_bases)
        self.assertGreaterEqual(len(patrol.locations), 1)
        self.assertEqual(local_patrol.kind, "patrol_location")
        self.assertEqual(defense.required_roles, ("front_line", "anchor"))
        self.assertEqual(
            match.missions,
            [recovery, mech_recovery, attack, patrol, local_patrol, defense],
        )

    def test_base_attack_mission_can_stamp_a_base_when_map_generation_did_not(self):
        match = Game(
            map_size=40, window_size=9, rng=random.Random(0), map_preset="badlands",
        ).create_match()
        self.assertFalse(match.mapFeatures.military_bases)

        attack = MissionGenerator(match).add_attack_military_base(match.teamList[1])

        self.assertEqual(attack.kind, "attack_military_base")
        self.assertEqual(len(match.mapFeatures.military_bases), 1)

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
