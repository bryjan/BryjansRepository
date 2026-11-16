"""Map terrain definitions and procedural world generation."""

from __future__ import annotations

import math
import random


# Plains, borders, and blank cells define a usable rectangular map, so only
# optional generated landscape types belong in this set.
GENERATABLE_TERRAINS = ("forest", "desert", "road", "suburb", "urban", "mountain")
DEFAULT_TERRAIN_ENABLED = {
    "forest": True,
    "desert": True,
    "road": True,
    "suburb": True,
    # Dense urban cover makes a dramatic tactical map, but it is intentionally
    # opt-in so ordinary skirmishes retain more open maneuver space.
    "urban": False,
    "mountain": False,
}


class MapGenerator:
    """Builds a map and attaches its terrain catalogue to a match.

    `match` is intentionally duck-typed here so world generation remains
    independent from match flow and combat rules.
    """

    DENSITY_MULTIPLIERS = {"None": 0, "Light": 1, "Normal": 2, "Thick": 3}

    def __init__(
        self, width: int, height: int | random.Random | None = None,
        rng: random.Random | None = None, terrain_enabled=None,
    ):
        # Preserve ``MapGenerator(size, rng)`` while also allowing rectangles.
        if isinstance(height, random.Random):
            rng = height
            height = None
        self.width = width
        self.height = width if height is None else height
        self.rng = rng if rng is not None else random.Random()
        self.terrain_enabled = self._terrain_options(terrain_enabled)
        if self.width < 8 or self.height < 8:
            raise ValueError("Maps must be at least 8 tiles wide and 8 tiles high.")

    @staticmethod
    def _terrain_options(overrides):
        """Merge optional terrain toggles while rejecting misspelled tile IDs."""
        if overrides is None:
            return dict(DEFAULT_TERRAIN_ENABLED)
        unknown = set(overrides) - set(GENERATABLE_TERRAINS)
        if unknown:
            raise ValueError(f"Unknown terrain toggle(s): {', '.join(sorted(unknown))}")
        return {
            terrain: bool(overrides.get(terrain, enabled))
            for terrain, enabled in DEFAULT_TERRAIN_ENABLED.items()
        }

    def build(self, match):
        # Delayed import avoids a cycle while the legacy domain module is being
        # transitioned into smaller modules.
        from .terrain import Cell, TerrainType

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
            # Dense buildings create the map's strongest static sensor cover.
            # Small and class-2 mechs can thread the streets freely, while
            # larger frames must force their way through or avoid the district.
            "urban": TerrainType("urban center", "#", "white", size=4,
                                 moveCostBySize=[0, 0, 0, 1, 3, 9999, 9999],
                                 visualAbsorbtion=30, radarAbsorbtion=60, radarSig=50),
            # Mountain patches are arduous for small frames, while larger
            # mechs can stride over the vegetation and rough ground. They
            # remain costly terrain even for the largest walking chassis.
            "mountain": TerrainType("mountain", "^", "white", size=5,
                                    moveCostBySize=[6, 5, 4, 3, 2, 2, 2],
                                    visualAbsorbtion=12, radarAbsorbtion=20,
                                    radarSig=100, fireproof=True),
            "road": TerrainType("road", "=", "dark_grey", moveCostBySize=[0] * 7,
                                visualAbsorbtion=1, radarAbsorbtion=0, radarSig=9999,
                                fireproof=True),
        }
        for name, value in terrain.items():
            setattr(match, name, value)

        # Grid storage is always rows first: grid[y][x]. Player-facing
        # positions remain [x, y], so every system can use one convention.
        grid = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                tile = terrain["border"] if x in (0, self.width - 1) or y in (0, self.height - 1) else terrain["plains"]
                row.append(Cell(tile, [x, y]))
            grid.append(row)
        for row in grid:
            for cell in row:
                cell.refNeighbors(grid)

        if self.terrain_enabled["forest"]:
            self._scatter(grid, terrain["forest"], "Normal")
        if self.terrain_enabled["desert"]:
            self._scatter(grid, terrain["desert"], "Light")
        if self.terrain_enabled["mountain"]:
            # Mountains use the same clustered growth method as forests, but
            # start less densely so they read as distinct ridges or patches.
            self._scatter(grid, terrain["mountain"], "Light")
        if self.terrain_enabled["road"]:
            self._roads(grid, terrain["road"], "Normal")
        if self.terrain_enabled["suburb"]:
            suburb_neighbors = [terrain["suburb"]]
            if self.terrain_enabled["road"]:
                suburb_neighbors.append(terrain["road"])
            self._associate(grid, terrain["suburb"], suburb_neighbors, "Normal")
        # Urban centers form dense pockets around developed road corridors,
        # rather than appearing as isolated buildings across open terrain.
        if self.terrain_enabled["urban"]:
            urban_neighbors = [terrain["urban"]]
            if self.terrain_enabled["road"]:
                urban_neighbors.append(terrain["road"])
            if self.terrain_enabled["suburb"]:
                urban_neighbors.append(terrain["suburb"])
            # An urban-only map still needs seed districts before it can grow.
            if len(urban_neighbors) == 1:
                self._scatter(grid, terrain["urban"], "Light")
            self._associate(grid, terrain["urban"], urban_neighbors, "Thick")
        return grid

    def _scatter(self, grid, terrain, density):
        multiplier = self._density_multiplier(density)
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
        multiplier = self._density_multiplier(density)
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
        multiplier = self._density_multiplier(density)
        for _ in range(multiplier):
            start, end = self._distant_cells(grid)
            self._draw_road(grid, start, end, terrain)

    def _density_multiplier(self, density):
        """Translate a readable map-density setting into a generation count."""
        try:
            return self.DENSITY_MULTIPLIERS[density]
        except KeyError as error:
            valid = ", ".join(self.DENSITY_MULTIPLIERS)
            raise ValueError(f"Unknown density {density!r}; choose one of: {valid}.") from error

    def _distant_cells(self, grid):
        while True:
            start = [self.rng.randrange(2, self.width - 2), self.rng.randrange(2, self.height - 2)]
            end = [self.rng.randrange(2, self.width - 2), self.rng.randrange(2, self.height - 2)]
            if math.dist(start, end) >= min(self.width, self.height) / 2:
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
