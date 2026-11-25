"""Debug inspection is paginated and does not alter fog or enemy report state."""

import random
import unittest
from unittest.mock import patch

from mechgame.runner import Game
from mechgame.commands.debug import enemy_orders, enemy_logs, inspect_enemy
from mechgame.ai import execute_squad_combat, execute_squad_movement


class AIDebugTests(unittest.TestCase):
    def setUp(self):
        self.match = Game(map_size=40, window_size=9, rng=random.Random(1)).create_match()
        self.enemy = self.match.teamList[1].squadsList[0]

    def test_orders_and_logs_include_enemy_decisions_and_reports(self):
        execute_squad_combat(self.match, self.enemy)
        execute_squad_movement(self.match, self.enemy)
        self.enemy.reportLog.append(["Enemy test report", True, False])
        orders = "\n".join(enemy_orders(self.match))
        logs = "\n".join(enemy_logs(self.match))
        self.assertIn(self.enemy.name, orders)
        self.assertIn("Order:", orders)
        self.assertIn("Combat:", logs)
        self.assertIn("Movement:", logs)
        self.assertIn("Enemy test report", logs)

    def test_debug_pages_do_not_reveal_terrain_or_mark_enemy_reports_read(self):
        report = ["Enemy secret report", True, False]
        self.enemy.reportLog.append(report)
        player = self.match.pov.team
        explored = set(player.exploredTiles)
        with patch("builtins.input", side_effect=["n", "p", "x"]), patch("mechgame.commands.debug.pv.print_overview") as render:
            inspect_enemy(self.match, logs=True)
        self.assertEqual(render.call_count, 3)
        self.assertFalse(report[2])
        self.assertEqual(player.exploredTiles, explored)
        self.assertFalse(player.mapVisibility.debug_reveal_all)
        self.assertFalse(self.match.turnEnded)

    def test_log_history_is_bounded(self):
        for index in range(250):
            self.enemy.logAI(self.match, str(index))
        self.assertEqual(len(self.enemy.aiLog), 200)


if __name__ == "__main__":
    unittest.main()
