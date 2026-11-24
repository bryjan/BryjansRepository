"""Coverage for the first visibility-limited AI combat pass."""

import math
import random
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from mechgame.ai import (
    _best_dps_approach, _move_into_weapon_range,
    execute_squad_combat, execute_squad_flee, execute_squad_movement,
    request_reinforcement,
)
from mechgame.runner import Game
from mechgame.teams import Squad
from mechgame import ambush
from mechgame import radar
from mechgame import coordination


class AiCombatTests(unittest.TestCase):
    def test_equal_enemy_force_encourages_linked_ambushes(self):
        squad = self.enemy_squad
        wing_mech = squad.mechList[-1]
        squad.mechList = [squad.squadLead]
        wing = Squad("Wing", [wing_mech], "Combat")
        wing.team = squad.team
        squad.team.squadsList.append(wing)
        squad.squadLead.pos = [10, 10]
        wing_mech.pos = [16, 10]
        for member in (squad, wing):
            member.combatForce = .8
            member.combatEffective = True
        wing_mech.directlyVisibleEnemies = wing_mech.trackedEnemies = [self.target]
        self.target.pos = [20, 10]
        team = squad.team
        team.mapVisibility.show_all_terrain = True
        self.match.mapFeatures.tactical_locations = [SimpleNamespace(marker_tiles=((13, 10),), tiles=((13, 10),))]
        for x in (11, 15):
            self.match.map[10][x].terrain = self.match.forest
        self.assertTrue(coordination.prefer_ambush(self.match, team, [squad, wing]))
        self.assertIsNotNone(squad.ambushLocation)
        self.assertIsNotNone(wing.ambushLocation)
        self.assertGreaterEqual(math.dist(squad.ambushLocation, wing.ambushLocation), 3)
        self.assertIn(wing, squad.ambushGroup)
        # Taking damage springs the first ambush and its supporting squad.
        squad.damageReceived += 1
        ambush.update(self.match, squad)
        self.assertTrue(squad.ambushTriggered)
        self.assertTrue(wing.ambushTriggered)

    def test_linked_ambush_release_excludes_a_withdrawing_squad(self):
        squad = self.enemy_squad
        wing_mech = squad.mechList[-1]
        squad.mechList.remove(wing_mech)
        wing = Squad("Wing", [wing_mech], "Combat")
        wing.team = squad.team
        squad.beginAmbush((10, 10))
        wing.beginAmbush((14, 10))
        squad.ambushGroup = wing.ambushGroup = (squad, wing)
        wing.orderFlee()
        squad.releaseAmbush()
        self.assertTrue(squad.ambushTriggered)
        self.assertFalse(wing.ambushTriggered)

    def test_attack_projection_uses_stored_radar_motion(self):
        team = self.enemy_squad.team
        for mech in self.enemy_squad.mechList:
            mech.directlyVisibleEnemies = []
        team.radarContacts[self.target] = {
            "position": [20, 20], "turn_start_pos": [18, 20],
            "speed": 2, "level": 3, "observed_round": 0,
        }
        self.target.pos = [35, 35]
        fix = coordination.observed_fix(self.match, team, self.target)
        self.assertEqual(coordination.projected_position(self.match, fix), (22, 20))
        self.match.matchRound = 5
        self.assertEqual(coordination.projected_position(self.match, fix), (26, 20))
        team.radarContacts[self.target]["level"] = 1
        fix = coordination.observed_fix(self.match, team, self.target)
        self.assertEqual(coordination.projected_position(self.match, fix), (20, 20))

    def test_ambush_preference_requires_known_cover_and_no_recent_engagement(self):
        squad = self.enemy_squad
        team = squad.team
        squad.squadLead.pos = [10, 10]
        team.exploredTiles = set()
        team.mapVisibility.show_all_terrain = False
        self.match.mapFeatures.tactical_locations = [SimpleNamespace(marker_tiles=((13, 10),), tiles=((13, 10),))]
        self.match.map[10][12].terrain = self.match.forest
        self.assertFalse(coordination.prefer_ambush(self.match, team, [squad]))
        team.exploredTiles.add((12, 10))
        team.lastEngagedRound = self.match.matchRound
        self.assertFalse(coordination.prefer_ambush(self.match, team, [squad]))
        team.lastEngagedRound = -100
        self.assertTrue(coordination.prefer_ambush(self.match, team, [squad]))
        self.assertEqual(squad.ambushLocation, (12, 10))

    def test_stage_attack_releases_and_remembers_lost_contact(self):
        squad = self.enemy_squad
        wing_mech = squad.mechList[-1]
        squad.mechList.remove(wing_mech)
        wing = Squad("Wing", [wing_mech], "Combat")
        wing.team = squad.team
        squad.team.squadsList.append(wing)
        squad.team.mapVisibility.show_all_terrain = True
        squad.squadLead.pos = [10, 10]
        wing_mech.pos = [16, 10]
        wing_mech.directlyVisibleEnemies = wing_mech.trackedEnemies = [self.target]
        order = squad.team.orderStageAttack(self.match, [squad, wing], [self.target])
        coordination.update(self.match, squad.team)
        self.assertEqual(order.state, "staging")
        for member in order.squads:
            for mech in member.mechList:
                mech.pos = list(order.staging_positions[member])
                mech.energy = mech.mechClass.energyMax
        coordination.update(self.match, squad.team)
        self.assertEqual(order.state, "attacking")
        self.assertIs(squad.primaryTarget, self.target)
        self.assertIs(wing.primaryTarget, self.target)
        for member in order.squads:
            for mech in member.mechList:
                mech.directlyVisibleEnemies = mech.trackedEnemies = []
        last_known = order.target_positions[self.target]
        self.target.pos = [38, 38]
        coordination.update(self.match, squad.team)
        self.assertEqual(order.state, "attacking")
        self.assertEqual(order.target_positions[self.target], last_known)
        self.assertIsNone(wing.primaryTarget)
        # A coordinated order releases in place, without staging positions.
        wing_mech.directlyVisibleEnemies = [self.target]
        immediate = squad.team.orderCombinedAttack(self.match, [squad, wing], [self.target])
        self.assertEqual(immediate.state, "attacking")
        self.assertEqual(immediate.staging_positions, {})

    def test_passive_detection_warning_springs_an_ambush(self):
        detector = self.player_squad.squadLead
        detector.mechClass.passiveRadar = True
        detector.speed = 0
        detector.pos = [10, 10]
        emitter = self.enemy_squad.squadLead
        self.player_squad.beginAmbush((10, 10), wait_for_order=True)
        cell = self.match.map[10][10]
        cell.radarPower = 0
        radar.passive_detect(detector, self.match, emitter)
        self.assertFalse(self.player_squad.ambushTriggered)
        cell.radarPower = max(50, radar.entity_detection_threshold(detector.radarSig) * 2)
        radar.passive_detect(detector, self.match, emitter)
        self.assertTrue(self.player_squad.ambushTriggered)

    def test_ambush_waits_for_lance_range_then_releases(self):
        mech = next(mech for mech in self.player_squad.mechList if any(w.isMelee for w in mech.mechClass.gunList))
        squad = self.player_squad
        squad.mechList = [mech]
        squad.squadLead = mech
        target = self.enemy_squad.squadLead
        mech.pos = [10, 10]
        target.pos = [20, 10]
        mech.directlyVisibleEnemies = mech.trackedEnemies = [target]
        squad.team.orderAmbush(squad, (10, 10))
        mech.radarOn = True
        ambush.update(self.match, squad)
        self.assertFalse(squad.ambushTriggered)
        self.assertFalse(mech.radarOn)
        self.assertIs(squad.ambushMech, mech)
        target.pos = [11, 10]
        ambush.update(self.match, squad)
        self.assertTrue(squad.ambushTriggered)

    def test_ambush_releases_if_enemy_recedes_after_near_approach(self):
        mech = next(mech for mech in self.player_squad.mechList if any(w.isMelee for w in mech.mechClass.gunList))
        squad = self.player_squad
        squad.mechList = [mech]
        squad.squadLead = mech
        target = self.enemy_squad.squadLead
        mech.pos = [10, 10]
        target.pos = [13, 10]
        mech.directlyVisibleEnemies = mech.trackedEnemies = [target]
        squad.beginAmbush((10, 10))
        ambush.update(self.match, squad)
        self.assertFalse(squad.ambushTriggered)
        target.pos = [14, 10]
        ambush.update(self.match, squad)
        self.assertTrue(squad.ambushTriggered)

    def test_ambush_releases_on_damage_even_when_waiting_for_order(self):
        squad = self.enemy_squad
        squad.beginAmbush((10, 10), wait_for_order=True)
        squad.damageReceived += 1
        ambush.update(self.match, squad)
        self.assertTrue(squad.ambushTriggered)

    def _disable_sensor_bursts(self):
        """Keep authored contact lists stable in targeting/assessment tests."""
        for mech in self.match.entities:
            for ability in mech.mechClass.hull.abilities:
                if ability.name == "Sensor Overdrive":
                    override = patch.object(ability, "try_ai_use", return_value=False)
                    override.start()
                    self.addCleanup(override.stop)

    def test_overdrive_searches_for_squadmates_of_class_two_and_three_contacts(self):
        mech = next(mech for mech in self.enemy_squad.mechList if mech.mechClass.name == "Kestrel")
        ability = mech.mechClass.hull.abilities[0]
        mech.directlyVisibleEnemies = [self.target]
        mech.trackedEnemies = [self.target]
        with patch.object(ability, "use", return_value=True):
            for size in (2, 3):
                self.target.size = size
                self.assertTrue(ability.try_ai_use(self.match, mech))
            self.target.size = 4
            self.assertFalse(ability.try_ai_use(self.match, mech))

    def test_sensor_overdrive_ai_triggers_and_energy_floor(self):
        mech = next(mech for mech in self.enemy_squad.mechList if mech.mechClass.name == "Kestrel")
        ability = mech.mechClass.hull.abilities[0]
        mech.directlyVisibleEnemies = []
        mech.trackedEnemies = [self.target]
        mech.noteCombat("enemy detected")
        with patch.object(ability, "use", return_value=True) as use:
            self.assertTrue(ability.try_ai_use(self.match, mech))
            mech.trackedEnemies = []
            self.assertTrue(ability.try_ai_use(self.match, mech))
            mech.energy = mech.mechClass.energyMax * .5 + ability.energyCost - 1
            self.assertFalse(ability.try_ai_use(self.match, mech))
            self.assertEqual(use.call_count, 2)

    def test_sensor_overdrive_scouts_every_third_turn_and_respects_stealth(self):
        mech = next(mech for mech in self.enemy_squad.mechList if mech.mechClass.name == "Kestrel")
        ability = mech.mechClass.hull.abilities[0]
        mech.directlyVisibleEnemies = mech.trackedEnemies = []
        with patch.object(ability, "use", return_value=True):
            mech.turnsStarted = 2
            self.assertFalse(ability.try_ai_use(self.match, mech))
            mech.turnsStarted = 3
            self.assertTrue(ability.try_ai_use(self.match, mech))
            mech.squad.setCombatPosture("stealth")
            self.assertFalse(ability.try_ai_use(self.match, mech))

    def test_sensor_overdrive_searches_after_observed_explosion(self):
        mech = next(mech for mech in self.enemy_squad.mechList if mech.mechClass.name == "Kestrel")
        ability = mech.mechClass.hull.abilities[0]
        mortar = next(mech for mech in self.player_squad.mechList if mech.hasArtillery)
        mech.directlyVisibleEnemies = [mortar]
        mech.trackedEnemies = []
        mech.explosionAlert = True
        with patch.object(ability, "use", return_value=True):
            self.assertFalse(ability.try_ai_use(self.match, mech))
            mech.directlyVisibleEnemies = []
            self.assertTrue(ability.try_ai_use(self.match, mech))
            self.assertFalse(mech.explosionAlert)

    def test_field_repair_ai_triggers_only_outside_combat(self):
        mech = self.enemy_squad.squadLead
        ability = mech.mechClass.hull.abilities[0]
        mech.cockpit.status = 1
        mech.noteCombat("taking damage")
        self.assertFalse(ability.try_ai_use(self.match, mech))
        mech.inCombat = False
        self.assertTrue(ability.try_ai_use(self.match, mech))
        self.assertEqual(mech.cockpit.status, 2)
        self.assertEqual(ability.charges, 0)

    def test_field_repair_needs_two_limbs_strictly_below_75_percent(self):
        mech = self.enemy_squad.squadLead
        ability = mech.mechClass.hull.abilities[0]
        limbs = mech.mechClass.limbList
        limbs[0].limbCon = .74
        limbs[1].limbCon = .75
        self.assertFalse(ability.try_ai_use(self.match, mech))
        limbs[1].limbCon = .74
        self.assertTrue(ability.try_ai_use(self.match, mech))
        self.assertEqual(limbs[0].limbCon, 1)
        self.assertEqual(limbs[1].limbCon, 1)

    def test_dash_reserves_last_charge_for_combat_retreat(self):
        mech = next(
            mech for mech in self.player_squad.mechList
            if any(weapon.isMelee for weapon in mech.mechClass.gunList)
        )
        ability = mech.mechClass.hull.abilities[0]
        target = self.enemy_squad.squadLead
        mech.pos = [10, 10]
        target.pos = [16, 10]
        mech.directlyVisibleEnemies = [target]
        mech.trackedEnemies = [target]
        mech.noteCombat("enemy in visual range")
        self.assertTrue(ability.try_ai_use(self.match, mech))
        self.assertLess(math.dist(mech.pos, target.pos), 6)
        self.assertEqual(ability.charges, 1)
        mech.clearTurnAbilities()
        self.assertFalse(ability.try_ai_use(self.match, mech))
        distance = math.dist(mech.pos, target.pos)
        self.assertTrue(ability.try_ai_use(self.match, mech, retreating=True))
        self.assertGreater(math.dist(mech.pos, target.pos), distance)
        self.assertEqual(ability.charges, 0)

    def test_dash_does_not_trigger_outside_combat_or_distance_band(self):
        mech = next(
            mech for mech in self.player_squad.mechList
            if any(weapon.isMelee for weapon in mech.mechClass.gunList)
        )
        ability = mech.mechClass.hull.abilities[0]
        target = self.enemy_squad.squadLead
        mech.pos = [10, 10]
        target.pos = [16, 10]
        mech.directlyVisibleEnemies = [target]
        self.assertFalse(ability.try_ai_use(self.match, mech))
        mech.noteCombat("enemy in visual range")
        target.pos = [20, 10]
        self.assertFalse(ability.try_ai_use(self.match, mech))

    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(0)).create_match()
        for row in self.match.map:
            for cell in row:
                cell.terrain = self.match.plains
        self.enemy_squad = self.match.teamList[1].squadsList[0]
        self.player_squad = self.match.teamList[0].squadsList[0]
        self.target = self.player_squad.squadLead
        self.target.pos = [12, 10]
        for index, mech in enumerate(self.enemy_squad.mechList):
            mech.pos = [10 - index * 3, 10]
            mech.directlyVisibleEnemies = [self.target]
            mech.trackedEnemies = [self.target]

    def test_ai_fires_at_a_visual_enemy_with_a_direct_weapon(self):
        starting_ap = [mech.ap for mech in self.enemy_squad.mechList]
        player_pov = self.match.pov

        fired = execute_squad_combat(self.match, self.enemy_squad)

        self.assertTrue(fired)
        self.assertTrue(any(mech.ap < ap for mech, ap in zip(self.enemy_squad.mechList, starting_ap)))
        self.assertTrue(all(mech.inCombat for mech in fired))
        self.assertIs(self.match.pov, player_pov)

    def test_high_reserve_mech_spends_remaining_ap_on_direct_fire(self):
        """Healthy ammunition and energy reserves permit sustained fire."""
        squad = self.enemy_squad
        shooter = squad.squadLead
        squad.mechList = [shooter]
        shooter.squad = squad
        shooter.pos = [10, 10]
        shooter.directlyVisibleEnemies = [self.target]
        shooter.trackedEnemies = [self.target]
        for limb in self.target.mechClass.limbList:
            limb.hp = limb.startingHP = 1_000
        chain_gun = next(
            weapon for weapon in shooter.mechClass.gunList
            if weapon.name == "Sustained ChainGun"
        )
        starting_charges = chain_gun.charges

        execute_squad_combat(self.match, squad)

        self.assertLessEqual(chain_gun.charges, starting_charges - 2)

    def test_double_time_and_retreat_suppress_ai_fire(self):
        self.enemy_squad.setMovementPolicy(mode="double_time")
        starting_ap = [mech.ap for mech in self.enemy_squad.mechList]

        self.assertEqual(execute_squad_combat(self.match, self.enemy_squad), [])
        self.assertEqual([mech.ap for mech in self.enemy_squad.mechList], starting_ap)

        self.enemy_squad.setMovementPolicy(mode="move")
        self.enemy_squad.setCombatPosture("retreat")
        self.assertEqual(execute_squad_combat(self.match, self.enemy_squad), [])
        self.assertEqual([mech.ap for mech in self.enemy_squad.mechList], starting_ap)

    def test_retreating_squad_calls_in_range_smoke_support(self):
        """A squad in contact asks a separate artillery squad to screen it."""
        retreating_squad = self.player_squad
        retreating_squad.playerControlled = False
        mortar = next(
            mech for mech in retreating_squad.mechList
            if any(weapon.isLauncher for weapon in mech.mechClass.gunList)
        )
        retreating_squad.mechList.remove(mortar)
        support_squad = Squad("Support", [mortar], "Artillery")
        self.match.teamList[0].squadsList.append(support_squad)
        support_squad.team = self.match.teamList[0]
        retreating_squad.squadLead.pos = [15, 10]
        mortar.pos = [10, 10]
        retreating_squad.squadLead.noteCombat("enemy in visual range")
        retreating_squad.setCombatPosture("retreat")

        self.assertEqual(execute_squad_combat(self.match, retreating_squad), [])
        self.assertEqual(support_squad.smokeCallPosition, (15, 10))
        self.assertEqual(support_squad.smokeCallTurns, 1)

        execute_squad_combat(self.match, support_squad)

        launcher = next(weapon for weapon in mortar.mechClass.gunList if weapon.isLauncher)
        self.assertEqual(launcher.selected_ammo.payload, "smoke")
        self.assertTrue(self.match.pendingImpacts)

    def test_flee_order_moves_an_ai_mech_to_the_border_and_preserves_it(self):
        """An ordered withdrawal exits intact rather than ejecting or dying."""
        squad = self.enemy_squad
        mech = squad.squadLead
        squad.mechList = [mech]
        mech.squad = squad
        mech.pos = [1, 10]
        for entity in self.match.entities:
            if entity is not mech:
                entity.pos = [20, 20]
        squad.orderFlee()

        moved = execute_squad_flee(self.match, squad)

        self.assertIn(mech, moved)
        self.assertTrue(mech.fled)
        self.assertTrue(mech.pilot.returned)
        self.assertEqual(mech.pilot.status, "RTB")
        self.assertIn(mech, self.match.fledMechs)
        self.assertNotIn(mech, self.match.destroyedMechs)
        self.assertNotIn(mech, self.match.entities)

    def test_spent_artillery_without_team_supplies_marks_itself_for_fleeing(self):
        mortar = next(
            mech for mech in self.player_squad.mechList
            if "artillery" in mech.mechClass.roles
        )
        for weapon in mortar.mechClass.gunList:
            for ammo in weapon.ammoTypes:
                ammo.charges = 0
        self.match.teamList[0].supplies = 0

        mortar.refreshReadiness(self.match)

        self.assertFalse(mortar.hasAvailableRole)
        self.assertTrue(mortar.shouldFlee)

    def test_low_ammo_mech_needs_attack_order_to_fire_on_radar_contact(self):
        self._disable_sensor_bursts()
        shooter = self.enemy_squad.mechList[-1]
        shooter.directlyVisibleEnemies = []
        shooter.trackedEnemies = [self.target]
        for weapon in shooter.mechClass.gunList:
            if not weapon.isLauncher and not weapon.isMelee:
                weapon.charges = 1
        self.match.issueTeamObjective(
            self.match.teamList[1], "defend", 80, (10, 10), "Hold position.",
        )
        original_ap = shooter.ap

        execute_squad_combat(self.match, self.enemy_squad)
        self.assertEqual(shooter.ap, original_ap)

        self.enemy_squad.setCombatPosture("attack")
        execute_squad_combat(self.match, self.enemy_squad)
        self.assertLess(shooter.ap, original_ap)

    def test_melee_weapon_is_used_against_a_close_visual_target(self):
        self._disable_sensor_bursts()
        shooter = self.enemy_squad.mechList[-1]
        shooter.pos = [10, 10]
        self.target.pos = [11, 10]
        shooter.directlyVisibleEnemies = [self.target]
        shooter.trackedEnemies = [self.target]
        for weapon in shooter.mechClass.gunList:
            if not weapon.isMelee and not weapon.isLauncher and weapon.charges is not None:
                weapon.charges = 0
        starting_ap = shooter.ap

        fired = execute_squad_combat(self.match, self.enemy_squad)

        self.assertIn(shooter, fired)
        self.assertEqual(shooter.lastFiredAt, self.target.pos)
        self.assertLess(shooter.ap, starting_ap)

    def test_melee_mech_closes_when_its_lance_beats_sidearm_dps(self):
        """A stronger short-range weapon preserves AP to close before firing."""
        squad = self.player_squad
        squad.playerControlled = False
        mech = next(
            entity for entity in squad.mechList
            if any(weapon.isMelee for weapon in entity.mechClass.gunList)
        )
        squad.mechList = [mech]
        squad.squadLead = mech
        mech.squad = squad
        target = self.enemy_squad.squadLead
        mech.pos = [10, 10]
        target.pos = [13, 10]
        mech.directlyVisibleEnemies = [target]
        mech.trackedEnemies = [target]
        for entity in self.match.entities:
            if entity not in {mech, target}:
                entity.pos = [30, 30]
        starting_ap = mech.ap

        execute_squad_combat(self.match, squad)

        self.assertIs(mech.approachTarget, target)
        self.assertEqual(mech.ap, starting_ap)
        execute_squad_movement(self.match, squad)
        lance = next(weapon for weapon in mech.mechClass.gunList if weapon.isMelee)
        self.assertLessEqual(math.dist(mech.pos, target.pos), lance.maxRange)

    def test_direct_weapon_approaches_can_span_multiple_turns(self):
        """Melee and ranged combinations share the same approach planner."""
        mech = next(
            entity for entity in self.player_squad.mechList
            if any(weapon.isMelee for weapon in entity.mechClass.gunList)
        )
        target = self.enemy_squad.squadLead
        weapon = next(weapon for weapon in mech.mechClass.gunList if weapon.isMelee)
        for reach, melee in ((1.5, True), (4, False), (None, False)):
            with self.subTest(reach=reach):
                weapon.maxRange = reach
                weapon.isMelee = melee
                weapon.accuracy = 3 if reach is None else 13
                mech.pos = [10, 10]
                target.pos = [24, 10]
                mech.directlyVisibleEnemies = [target]
                mech.trackedEnemies = [target]
                for entity in self.match.entities:
                    if entity not in {mech, target}:
                        entity.pos = [35, 35]
                for _ in range(8):
                    mech.ap = mech.mechClass.apMax
                    mech.mp = mech.mechClass.mpMax
                    mech.energy = mech.mechClass.energyMax
                    mech.speed = 0
                    approach = _best_dps_approach(self.match, mech)
                    if approach is None:
                        break
                    self.assertIs(approach[2], weapon)
                    mech.approachTarget = target
                    mech.approachWeapon = weapon
                    self.assertTrue(_move_into_weapon_range(self.match, mech, "move"))
                self.assertLess(math.dist(mech.pos, target.pos), 14)
                if reach is not None:
                    self.assertLessEqual(math.dist(mech.pos, target.pos), reach)

    def test_artillery_launches_after_an_unclear_two_turn_review(self):
        squad = self.player_squad
        squad.playerControlled = False
        mortar = next(
            mech for mech in squad.mechList
            if any(weapon.isLauncher for weapon in mech.mechClass.gunList)
        )
        support = next(
            mech for mech in squad.mechList if "anti_heavy" in mech.mechClass.roles
        )
        squad.mechList = [support, mortar]
        squad.squadLead = support
        support.squad = squad
        mortar.squad = squad
        squad.refreshCombatForce()
        support.pos = [9, 10]
        mortar.pos = [10, 10]
        for index, friendly in enumerate(self.match.entities):
            if friendly not in {support, mortar}:
                friendly.pos = [2, 2 + index]
        self.target = self.enemy_squad.squadLead
        self.target.pos = [15, 10]
        mortar.directlyVisibleEnemies = [self.target]
        mortar.trackedEnemies = [self.target]
        support.noteCombat("enemy in visual range")
        mortar.noteCombat("enemy in visual range")

        execute_squad_combat(self.match, squad)
        self.assertEqual(self.match.pendingImpacts, [])
        execute_squad_combat(self.match, squad)
        self.assertTrue(self.match.pendingImpacts)

    def test_overwhelming_observed_force_orders_contact_avoidance(self):
        squad = self.player_squad
        squad.playerControlled = False
        squad.squadLead.pos = [10, 10]
        # This test isolates force assessment from the new sustained-fire
        # behavior; damaged weapons leave the observed enemy force intact.
        for mech in squad.mechList:
            for weapon in mech.mechClass.gunList:
                weapon.hp = 0
        for index, enemy in enumerate(self.enemy_squad.mechList):
            enemy.pos = [14 + index, 10]
        squad.squadLead.directlyVisibleEnemies = list(self.enemy_squad.mechList)
        squad.squadLead.trackedEnemies = list(self.enemy_squad.mechList)
        squad.squadLead.noteCombat("enemy in visual range")

        execute_squad_combat(self.match, squad)
        execute_squad_combat(self.match, squad)

        self.assertTrue(squad.avoidContact)
        self.assertIsNotNone(squad.avoidanceTarget)

    def test_anti_heavies_share_a_near_matching_combat_target(self):
        squad = self.player_squad
        squad.playerControlled = False
        anti_heavies = [
            mech for mech in squad.mechList if "anti_heavy" in mech.mechClass.roles
        ]
        target = next(mech for mech in self.enemy_squad.mechList if mech.size == 3)
        target.pos = [14, 10]
        for index, mech in enumerate(anti_heavies):
            mech.pos = [10 - index * 3, 10]
            mech.directlyVisibleEnemies = [target]
            mech.trackedEnemies = [target]

        execute_squad_combat(self.match, squad)

        self.assertTrue(anti_heavies)
        self.assertTrue(all(squad.assignedTargets.get(mech) is target for mech in anti_heavies))

    def test_anti_swarm_mech_opportunistically_prioritizes_a_damaged_target(self):
        self._disable_sensor_bursts()
        swarm_mech = next(
            mech for mech in self.enemy_squad.mechList if "anti_swarm" in mech.mechClass.roles
        )
        close_target = self.player_squad.mechList[1]
        damaged_target = self.player_squad.mechList[2]
        swarm_mech.pos = [10, 10]
        close_target.pos = [11, 10]
        damaged_target.pos = [14, 10]
        close_target.mechClass.condition = 100
        damaged_target.mechClass.condition = 20
        swarm_mech.directlyVisibleEnemies = [close_target, damaged_target]
        swarm_mech.trackedEnemies = [close_target, damaged_target]

        execute_squad_combat(self.match, self.enemy_squad)

        self.assertIs(self.enemy_squad.assignedTargets[swarm_mech], damaged_target)

    def test_leader_waits_two_combat_turns_before_damage_assessment(self):
        self._disable_sensor_bursts()
        squad = self.enemy_squad
        leader = squad.squadLead
        # Keep the observed contact outside all direct weapon ranges. The
        # test supplies damage figures directly and should not resolve fire.
        self.target.pos = [39, 10]
        leader.noteCombat("enemy in visual range")
        leader.directlyVisibleEnemies = [self.target]
        leader.trackedEnemies = [self.target]
        squad.damageGiven = 20
        squad.damageReceived = 5

        execute_squad_combat(self.match, squad)
        self.assertEqual(squad.engagementAssessment, "unassessed")
        self.assertEqual(squad.combatTurns, 1)

        execute_squad_combat(self.match, squad)

        self.assertEqual(squad.engagementAssessment, "favorable")
        self.assertGreater(squad.estimatedDamageGiven, squad.estimatedDamageReceived)
        self.assertIs(squad.primaryTarget, self.target)

    def test_player_squad_receives_a_critical_reinforcement_request(self):
        request_reinforcement(self.match, self.enemy_squad, self.player_squad)

        self.assertIs(self.player_squad.reinforcementRequest, self.enemy_squad)
        self.assertTrue(any(
            critical and "Reinforcement request" in message
            for message, critical, _ in self.player_squad.reportLog
        ))

    def test_attack_order_marks_a_low_accuracy_contact_for_approach(self):
        self._disable_sensor_bursts()
        target = self.target
        target.pos = [35, 10]
        for index, mech in enumerate(self.enemy_squad.mechList):
            mech.pos = [5 - index * 3, 10]
            mech.directlyVisibleEnemies = []
            mech.trackedEnemies = [target]
        self.enemy_squad.setCombatPosture("attack")
        leader = self.enemy_squad.squadLead

        execute_squad_combat(self.match, self.enemy_squad)

        self.assertIs(self.enemy_squad.primaryTarget, target)
        execute_squad_movement(self.match, self.enemy_squad)
        self.assertGreater(leader.pos[0], 5)


if __name__ == "__main__":
    unittest.main()
