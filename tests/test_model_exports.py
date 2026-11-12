import unittest

import gameClasses
from mechgame import models
from mechgame.entities import Entity
from mechgame.match import MatchInfo
from mechgame.mechs import MechClass
from mechgame.terrain import Cell
from mechgame.teams import Squad


class ModelExportTests(unittest.TestCase):
    def test_compatibility_modules_export_the_focused_models(self):
        self.assertIs(models.MatchInfo, MatchInfo)
        self.assertIs(models.Cell, Cell)
        self.assertIs(models.Entity, Entity)
        self.assertIs(models.MechClass, MechClass)
        self.assertIs(models.Squad, Squad)
        self.assertIs(gameClasses.MatchInfo, MatchInfo)
        self.assertIs(gameClasses.Entity, Entity)
