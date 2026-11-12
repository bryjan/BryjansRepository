"""Map terrain definitions and procedural world generation."""

from __future__ import annotations

import math
import random


class MapGenerator:
    """Builds a map and attaches its terrain catalogue to a match.

    `match` is intentionally duck-typed here so world generation remains
    independent from match flow and combat rules.
    """

    def __init__(self, size: int, rng: random.Random | None = None):
        self.size = size
        self.rng = rng or random.Random()

    def build(self, match):
        # Delayed import avoids a cycle while the legacy domain module is being
        # transitioned into smaller modules.
        from .models import Cell, TerrainType

        terrain = {
            "blank": TerrainType("blank", " ", "black", visualAbsorbtion=9999,
                                 radarAbsorbtion=9999, fireproof=True, passable=False),
            "border": TerrainType("border", "X", "white", moveCostBySize=[9999] * 7,
                                  visualAbsorbtion=1, radarAbsorbtion=1, radarSig=1,
                                  fireproof=True, passable=False),
            "desert": TerrainType("desert", "~", "yellow", moveCostBySize=[1, 2, 3, 2, 1, 1, 1],
                                  visualAbsorbtion=2, radarAbsorbtion=1, radarSig=9999, fireproof=True),
            "plains": TerrainType("plains", "_", "light_green", moveCostBySize=[1] * 7,
                                  visualAbsorbtion=1, radarAbsorbtion=1, radarSig=9999),
            "forest": TerrainType("forest", "t", "green", size=3,
                                  moveCostBySize=[1, 1, 2, 4, 3, 1, 1],
                                  visualAbsorbtion=6, radarAbsorbtion=15, radarSig=100),
            "suburb": TerrainType("suburbs", "H", "light_grey", size=3,
                                  moveCostBySize=[1, 1, 1, 5, 4, 2, 1],
                                  visualAbsorbtion=20, radarAbsorbtion=40, radarSig=80),
            "road": TerrainType("road", "=", "dark_grey", moveCostBySize=[0] * 7,
                                visualAbsorbtion=1, radarAbsorbtion=0, radarSig=9999,
                                fireproof=True),
        }
        for name, value in terrain.items():
            setattr(match, name, value)

        grid = []
        for y in range(self.size):
            row = []
            for x in range(self.size):
                tile = terrain["border"] if x in (0, self.size - 1) or y in (0, self.size - 1) else terrain["plains"]
                row.append(Cell(tile, [x, y]))
            grid.append(row)
        for row in grid:
            for cell in row:
                cell.refNeighbors(grid)

        self._scatter(grid, terrain["forest"], "Normal")
        self._scatter(grid, terrain["desert"], "Light")
        self._roads(grid, terrain["road"], "Normal")
        self._associate(grid, terrain["suburb"], [terrain["road"], terrain["suburb"]], "Normal")
        return grid

    def _scatter(self, grid, terrain, density):
        multiplier = {"None": 0, "Light": 1, "Normal": 2, "Thick": 3}[density]
        if not multiplier:
            return
        for row in grid[1:-1]:
            for cell in row[1:-1]:
                if self.rng.randint(1, 1000) <= 3 * multiplier:
                    cell.terrain = terrain
        for _ in range(multiplier):
            changes = []
            for row in grid[2:-2]:
                for cell in row[2:-2]:
                    neighbors = sum(neighbor.terrain is terrain for neighbor in cell.nList)
                    if neighbors and self.rng.randint(1, 100) + neighbors < 25:
                        changes.append(cell)
            for cell in changes:
                cell.terrain = terrain

    def _associate(self, grid, terrain, associated, density):
        multiplier = {"None": 0, "Light": 1, "Normal": 2, "Thick": 3}[density]
        for _ in range(multiplier):
            changes = []
            for row in grid[2:-2]:
                for cell in row[2:-2]:
                    neighbors = sum(neighbor.terrain in associated for neighbor in cell.nList)
                    if cell.terrain not in associated and neighbors and self.rng.randint(1, 100) + neighbors < 5:
                        changes.append(cell)
            for cell in changes:
                cell.terrain = terrain

    def _roads(self, grid, terrain, density):
        multiplier = {"None": 0, "Light": 1, "Normal": 2, "Thick": 3}[density]
        for _ in range(multiplier):
            start, end = self._distant_cells(grid)
            self._draw_road(grid, start, end, terrain)

    def _distant_cells(self, grid):
        while True:
            start = [self.rng.randrange(2, self.size - 2), self.rng.randrange(2, self.size - 2)]
            end = [self.rng.randrange(2, self.size - 2), self.rng.randrange(2, self.size - 2)]
            if math.dist(start, end) >= self.size / 2:
                return start, end

    def _draw_road(self, grid, start, end, terrain):
        x, y = start
        target_x, target_y = end
        while (x, y) != (target_x, target_y):
            grid[y][x].terrain = terrain
            if x != target_x and (y == target_y or self.rng.choice((True, False))):
                x += 1 if target_x > x else -1
            elif y != target_y:
                y += 1 if target_y > y else -1
        grid[target_y][target_x].terrain = terrain
