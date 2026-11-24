"""Queued fire missions use the chosen artillery unit's actual squad turn."""

import random
import unittest
from unittest.mock import patch

from mechgame.runner import Game
from mechgame.catalog import create_mech
from mechgame.entities import Entity, Pilot
from mechgame.teams import Squad
from mechgame import fire_missions, squad_orders
from mechgame.commands.orders import fireMissionMenu
from mechgame.ai import execute_squad_combat


class FireMissionTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(3)).create_match()
        self.original_pov = self.match.pov
        self.units = [Entity(create_mech("lancer.mortar"), Pilot(name)) for name in ("Low", "Full")]
        self.squad = Squad("Mortars", self.units, "Artillery", playerControlled=True)
        self.squad.team = self.original_pov.team
        self.squad.team.squadsList.append(self.squad)
        for index, mech in enumerate(self.units):
            mech.team = self.squad.team
            mech.pos = [10 + index * 3, 10]
        self.match.entities.extend(self.units)
        squad_orders.set_control(self.squad, ai=True)
        self.units[0].mechClass.gunList[0].ammoTypes[0].charges = 0

    def test_defaults_to_most_ammunition_and_can_switch_units(self):
        selected = []
        def launcher_menu(match, launcher, **kwargs):
            selected.append(match.pov)
            return "switch_artillery" if len(selected) == 1 else None
        with patch("mechgame.commands.firing.launcherFireMenu", side_effect=launcher_menu), patch("builtins.input", return_value="2"), patch("mechgame.commands.orders.pv.printPOV"):
            fireMissionMenu(self.match, self.squad)
        self.assertEqual(selected, [self.units[1], self.units[0]])
        self.assertIs(self.match.pov, self.original_pov)

    def test_launcher_menu_queues_without_spending_out_of_turn(self):
        mech = self.units[1]
        launcher = mech.mechClass.gunList[0]
        ammo = launcher.selected_ammo.charges
        ap = mech.ap
        with patch("builtins.input", side_effect=["c", "25,10", "", "x"]), patch("mechgame.commands.firing.pv.printPOV"), patch("builtins.print"):
            fireMissionMenu(self.match, self.squad)
        self.assertEqual(len(self.squad.fireMissions), 1)
        self.assertEqual(self.squad.fireMissions[0].position, (25, 10))
        self.assertEqual(mech.ap, ap)
        self.assertEqual(launcher.selected_ammo.charges, ammo)
        self.assertEqual(self.match.pendingImpacts, [])
        self.assertFalse(self.match.turnEnded)
        self.assertIs(self.match.pov, self.original_pov)
        execute_squad_combat(self.match, self.squad)
        self.assertEqual(mech.ap, ap - launcher.apCost)
        self.assertEqual(launcher.selected_ammo.charges, ammo - 1)
        self.assertEqual(len(self.match.pendingImpacts), 1)
        self.assertEqual(self.squad.fireMissions, [])

    def test_cancel_restores_player_view_without_queueing(self):
        with patch("builtins.input", return_value="x"), patch("mechgame.commands.firing.pv.printPOV"), patch("builtins.print"):
            fireMissionMenu(self.match, self.squad)
        self.assertIs(self.match.pov, self.original_pov)
        self.assertEqual(self.squad.fireMissions, [])

    def test_multiple_payloads_and_locations_remain_queued_until_cancel(self):
        mech = self.units[1]
        launcher = mech.mechClass.gunList[0]
        with patch("builtins.input", side_effect=["c", "25,10", "", "a", "2", "", "c", "26,10", "", "x"]), patch("mechgame.commands.firing.pv.printPOV"), patch("builtins.print"):
            fireMissionMenu(self.match, self.squad)
        self.assertEqual([order.ammo_index for order in self.squad.fireMissions], [0, 1, 1])
        self.assertEqual([order.position for order in self.squad.fireMissions], [(25, 10), (25, 10), (26, 10)])
        with self.assertRaises(ValueError):
            fire_missions.queue(self.match, mech, launcher, [27, 10])
        self.assertEqual(len(self.squad.fireMissions), 3)
        execute_squad_combat(self.match, self.squad)
        self.assertEqual(len(self.match.pendingImpacts), 3)
        self.assertEqual(mech.ap, 0)
        self.assertEqual(self.squad.fireMissions, [])

    def test_all_player_owned_squads_precede_enemy_squads(self):
        self.match.teamList.reverse()
        slots = self.match._turn_slots()
        self.assertTrue(slots[0][1].playerCommandable)
        self.assertIs(slots[1][1], self.squad)
        self.assertFalse(slots[-1][1].playerCommandable)
        _, next_squad, wrapped = self.match._next_operational_slot(self.original_pov.squad)
        self.assertIs(next_squad, self.squad)
        self.assertFalse(wrapped)
        _, next_squad, wrapped = self.match._next_operational_slot(slots[-1][1])
        self.assertIs(next_squad, self.original_pov.squad)
        self.assertTrue(wrapped)


if __name__ == "__main__":
    unittest.main()
