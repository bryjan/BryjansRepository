"""Unknown-source hits, sound snapshots, stale-area search and scouting shells."""

import random
import unittest

from mechgame.runner import Game
from mechgame import recon, artillery, effects
from mechgame.ai import execute_squad_combat, execute_squad_movement
from mechgame.catalog import create_mech
from mechgame.entities import Entity, Pilot
from mechgame.teams import Squad


class ReconTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(2)).create_match()
        self.squad = self.match.teamList[1].squadsList[0]
        self.team = self.squad.team
        self.shooter = self.match.playerSquad.squadLead
        for row in self.match.map:
            for cell in row:
                if cell.terrain is not self.match.border:
                    cell.terrain = self.match.plains
        for mech, position in zip(self.squad.mechList, ([10, 10], [7, 10], [7, 13])):
            mech.pos = list(position)
            mech.trackedEnemies = mech.directlyVisibleEnemies = []
        for mech in self.match.playerSquad.mechList:
            mech.pos = [35, 35]

    def test_unknown_artillery_hit_repositions_all_roles_without_waiting_for_recharge(self):
        mortar = Entity(create_mech("lancer.mortar"), Pilot("Support"))
        mortar.pos = [7, 7]
        mortar.squad, mortar.team = self.squad, self.team
        self.squad.mechList.append(mortar)
        self.match.entities.append(mortar)
        self.match.recordCombatDamage(self.shooter.team, self.squad.squadLead, 10, damage_source="explosion")
        starts = {mech: tuple(mech.pos) for mech in self.squad.mechList}
        for mech in self.squad.mechList:
            mech.energy = int(mech.mechClass.energyMax * .4)
        self.assertEqual(execute_squad_combat(self.match, self.squad), [])
        moved = execute_squad_movement(self.match, self.squad)
        self.assertEqual(set(moved), set(self.squad.mechList))
        self.assertTrue(all(tuple(mech.pos) != starts[mech] for mech in self.squad.mechList))

    def test_visible_attacker_and_environmental_fire_do_not_create_unknown_source(self):
        defender = self.squad.squadLead
        defender.directlyVisibleEnemies = [self.shooter]
        self.match.recordCombatDamage(self.shooter, defender, 10, damage_source="rifle")
        self.assertFalse(recon.emergency(self.match, self.squad))
        self.match.recordCombatDamage(None, defender, 5, damage_source="fire")
        self.assertFalse(recon.emergency(self.match, self.squad))

    def test_sound_bearing_is_snapshotted_without_hidden_shooter_coordinates(self):
        listener = self.squad.squadLead
        listener.mechClass.shareData = True
        self.shooter.pos = [27, 10]
        weapon = self.shooter.mechClass.gunList[0]
        weapon.soundReport = 18
        weapon.emitSound(self.match, self.shooter)
        sound = recon.latest_sound(self.match, self.squad)
        self.assertEqual(sound.direction, "East")
        self.assertNotEqual(sound.position, tuple(self.shooter.pos))
        self.shooter.pos = [2, 2]
        recon.prepare(self.match, self.squad)
        self.assertEqual(self.squad.investigationPosition, sound.position)
        execute_squad_movement(self.match, self.squad)
        self.assertGreater(listener.pos[0], 10)

    def test_search_prefers_oldest_visual_coverage_not_revealed_terrain(self):
        self.match.matchRound = 12
        self.team.mapVisibility.show_all_terrain = True
        self.team.lastSeenRound = {(x, y): 10 for x in range(40) for y in range(40)}
        for y in range(7, 13):
            for x in range(7, 13):
                self.team.lastSeenRound[(x, y)] = 1
        self.assertEqual(recon.oldest_area(self.match, self.squad, (20, 20)), (10, 10))
        listener = self.squad.squadLead
        listener.mechClass.shareData = True
        self.team.currentObservationRound = 12
        self.team.share_vision(listener, [self.match.map[10][10]])
        self.assertEqual(self.team.lastSeenRound[(10, 10)], 12)

    def test_manual_squad_is_warned_without_forced_movement(self):
        squad = self.match.playerSquad
        mech = squad.squadLead
        start = tuple(mech.pos)
        self.match.recordCombatDamage(self.team, mech, 5, damage_source="explosion")
        self.assertEqual(execute_squad_movement(self.match, squad), [])
        self.assertEqual(tuple(mech.pos), start)
        self.assertTrue(any("unknown source" in report[0] and report[1] for report in squad.reportLog))

    def test_scout_shells_only_reveal_after_landing_and_have_a_team_cooldown(self):
        mortar = Entity(create_mech("lancer.mortar"), Pilot("Recon Support"))
        support = Squad("Recon Battery", [mortar], "Artillery")
        support.team = mortar.team = self.team
        self.team.squadsList.append(support)
        self.match.entities.append(mortar)
        mortar.pos = [12, 10]
        self.team.searchUntilRound = 5
        launcher = mortar.mechClass.gunList[0]
        scout = next(ammo for ammo in launcher.ammoTypes if ammo.payload == "scout")
        charges = scout.charges
        self.assertEqual(recon.scout_fire(self.match, support), {mortar})
        self.assertEqual(scout.charges, charges - 1)
        self.assertEqual(recon.scout_fire(self.match, support), set())
        self.assertEqual(effects.scout_visible_cells(self.match, self.team), [])
        self.match.matchRound = self.match.pendingImpacts[0].impact_round
        artillery.advance_impacts(self.match)
        self.assertTrue(effects.scout_visible_cells(self.match, self.team))


if __name__ == "__main__":
    unittest.main()
