"""Map terrain definitions and procedural world generation."""

from __future__ import annotations

import math
import random


# Plains, borders, and blank cells define a usable rectangular map, so only
# optional generated landscape types belong in this set.
GENERATABLE_TERRAINS = (
    "forest", "desert", "road", "suburb", "urban", "mountain", "water",
    "river",
)
DEFAULT_TERRAIN_ENABLED = {
    "forest": True,
    "desert": True,
    "road": True,
    "suburb": True,
    # Everything starts enabled for map-generation testing. Individual maps
    # can still disable any optional terrain in the pre-match menu.
    "urban": True,
    "mountain": True,
    "water": True,
    "river": True,
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
                                 radarAbsorbtion=9999, fireproof=True, passable=False,
                                 overviewWeight=0),
            "border": TerrainType("border", "X", "white", moveCostBySize=[9999] * 7,
                                  visualAbsorbtion=1, radarAbsorbtion=1, radarSig=1,
                                  fireproof=True, passable=False, overviewWeight=100),
            # Heat haze makes long visual paths slightly less reliable than
            # open plains, without providing meaningful physical cover.
            "desert": TerrainType("desert", "~", "yellow", moveCostBySize=[1, 2, 3, 2, 1, 1, 1],
                                  visualAbsorbtion=1.2, radarAbsorbtion=1, radarSig=9999,
                                  fireproof=True, overviewWeight=1),
            "plains": TerrainType("plains", "_", "light_green", moveCostBySize=[1] * 7,
                                  visualAbsorbtion=1, radarAbsorbtion=1, radarSig=9999,
                                  overviewWeight=1),
            "forest": TerrainType("forest", "t", "green", size=3,
                                  moveCostBySize=[1, 1, 2, 4, 3, 1, 1],
                                  visualAbsorbtion=6, radarAbsorbtion=15, radarSig=100,
                                  overviewWeight=1.25),
            "suburb": TerrainType("suburbs", "H", "light_grey", size=3,
                                  moveCostBySize=[1, 1, 1, 5, 4, 2, 1],
                                  visualAbsorbtion=20, radarAbsorbtion=40, radarSig=80,
                                  overviewWeight=1.5),
            # Dense buildings create the map's strongest static sensor cover.
            # Small and class-2 mechs can thread the streets freely, while
            # larger frames must force their way through or avoid the district.
            "urban": TerrainType("urban center", "#", "white", size=4,
                                 moveCostBySize=[0, 0, 0, 1, 3, 9999, 9999],
                                 visualAbsorbtion=30, radarAbsorbtion=60, radarSig=50,
                                 overviewWeight=2.5),
            # Mountain patches are arduous for small frames, while larger
            # mechs can stride over the vegetation and rough ground. They
            # remain costly terrain even for the largest walking chassis.
            "mountain": TerrainType("mountain", "^", "white", size=5,
                                    moveCostBySize=[6, 5, 4, 3, 2, 2, 2],
                                    visualAbsorbtion=12, radarAbsorbtion=20,
                                    radarSig=100, overviewWeight=2.5),
            # Water is deliberately defined before river and pond generation.
            # It is sensor-clear, but only floating, flying, or titanic mechs
            # can enter it. The energy scale starts at one for sizes 0–2,
            # then rises by one each class through size 6.
            "water": TerrainType("water", "~", "cyan",
                                  moveCostBySize=[1, 1, 1, 2, 3, 4, 5],
                                  visualAbsorbtion=0, radarAbsorbtion=0,
                                  radarSig=9999, requireFloat=True, fireproof=True,
                                  overviewWeight=3),
            # Tunnels preserve mountain cover but give light and medium mechs
            # a road-like route through the pass. Larger frames still have to
            # force their way through as if crossing mountain terrain.
            "tunnel": TerrainType("tunnel", "T", "light_grey", size=5,
                                   moveCostBySize=[0, 0, 0, 0, 2, 2, 2],
                                   visualAbsorbtion=12, radarAbsorbtion=20,
                                   radarSig=100, fireproof=True, overviewWeight=3),
            "road": TerrainType("road", "=", "dark_grey", moveCostBySize=[0] * 7,
                                visualAbsorbtion=1, radarAbsorbtion=0, radarSig=9999,
                                fireproof=True, overviewWeight=3),
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

        # Mountains establish protected terrain first. Still water may replace
        # mountain cells. Roads cross both terrain types: over water as bridges
        # and through mountains as potential tunnels. Other passes preserve
        # the resulting special terrain.
        protected_terrain = ()
        if self.terrain_enabled["mountain"]:
            self._mountain_ranges(grid, terrain["mountain"])
            protected_terrain = (terrain["mountain"],)
        if self.terrain_enabled["water"]:
            self._still_water(grid, terrain["water"])
            protected_terrain = (*protected_terrain, terrain["water"])
        if self.terrain_enabled["river"]:
            self._rivers(grid, terrain["water"], terrain["mountain"])
            if terrain["water"] not in protected_terrain:
                protected_terrain = (*protected_terrain, terrain["water"])
        if self.terrain_enabled["forest"]:
            self._scatter(grid, terrain["forest"], "Normal", protected_terrain)
            if self.terrain_enabled["mountain"]:
                self._mountain_edge_forests(grid, terrain["mountain"], terrain["forest"])
        if self.terrain_enabled["desert"]:
            self._scatter(grid, terrain["desert"], "Light", protected_terrain)
        if self.terrain_enabled["road"]:
            self._roads(grid, terrain["road"], "Normal")
            if self.terrain_enabled["mountain"]:
                self._tunnel_passes(
                    grid, terrain["road"], terrain["mountain"], terrain["tunnel"],
                )
                protected_terrain = (*protected_terrain, terrain["tunnel"])
        if self.terrain_enabled["suburb"]:
            suburb_neighbors = [terrain["suburb"]]
            if self.terrain_enabled["road"]:
                suburb_neighbors.append(terrain["road"])
            self._associate(
                grid, terrain["suburb"], suburb_neighbors, "Normal", protected_terrain,
            )
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
                self._scatter(grid, terrain["urban"], "Light", protected_terrain)
            self._associate(
                grid, terrain["urban"], urban_neighbors, "Thick", protected_terrain,
            )
        return grid

    def _scatter(self, grid, terrain, density, protected_terrain=()):
        multiplier = self._density_multiplier(density)
        protected_terrain = set(protected_terrain)
        if not multiplier:
            return
        for row in grid[1:-1]:
            for cell in row[1:-1]:
                if (
                    cell.terrain not in protected_terrain
                    and self.rng.randint(1, 1000) <= 3 * multiplier
                ):
                    cell.terrain = terrain
        for _ in range(multiplier):
            changes = []
            for row in grid[2:-2]:
                for cell in row[2:-2]:
                    neighbors = sum(neighbor.terrain is terrain for neighbor in cell.nList)
                    if (
                        cell.terrain not in protected_terrain
                        and neighbors and self.rng.randint(1, 100) + neighbors < 25
                    ):
                        changes.append(cell)
            for cell in changes:
                cell.terrain = terrain

    def _mountain_ranges(self, grid, mountain):
        """Place peaks with zero to two short ridges for shaped ranges."""
        range_count = max(1, round((self.width * self.height) / 2500))
        for _ in range(range_count):
            peak = [
                self.rng.randrange(2, self.width - 2),
                self.rng.randrange(2, self.height - 2),
            ]
            # Keep the peak and each ridge independently irregular.  A range
            # can therefore have a compact core with a broad ridge, or the
            # reverse, instead of all of its features sharing one width.
            peak_width = 3 + self.rng.randint(0, 2)
            self._place_mountain_peak(grid, peak, mountain, peak_width)
            for _ in range(self.rng.randint(0, 2)):
                ridge_end = self._ridge_endpoint(peak)
                if ridge_end is not None:
                    self._draw_mountain_ridge(
                        grid,
                        peak,
                        ridge_end,
                        mountain,
                        self.rng.randint(2, 3) + self.rng.randint(0, 2),
                    )

    def _still_water(self, grid, water):
        """Generate sparse connected ponds.

        Rivers and their bank-side lakes are generated separately so lakes can
        be tied to a meaningful waterway rather than appearing at random.
        """
        for row in grid[1:-1]:
            for cell in row[1:-1]:
                # About one small pond seed per 1,600 interior tiles keeps
                # ponds rare on large maps and unusual on compact ones.
                if cell.terrain is not water and self.rng.randint(1, 1600) == 1:
                    self._grow_water_patch(grid, cell, water, self.rng.randint(3, 6))

    def _rivers(self, grid, water, mountain):
        """Add winding streams and scalable edge-to-edge large rivers."""
        # Broad rivers cross the full map, so their density must scale with
        # map span rather than raw area. A roughly 100×100 map gets one; much
        # larger maps can still receive more without a fixed global cap.
        large_river_count = self._scaled_linear_feature_count(100)
        large_river_cells = []
        for _ in range(large_river_count):
            large_river_cells.extend(self._large_river(grid, water, width=3))
        # Lake attempts retain the requested area-scaled rate, but cannot
        # exceed the number of broad rivers available to feed them.
        lake_count = min(large_river_count, self._scaled_feature_count(1000))
        for _ in range(lake_count):
            self._lake_beside_large_river(grid, water, large_river_cells)
        # Small tributary-like streams are deliberately less common. They may
        # begin in mountain terrain or enter from an edge, then end naturally.
        for _ in range(self._scaled_linear_feature_count(50)):
            self._small_river(grid, water, mountain)

    def _scaled_feature_count(self, tiles_per_feature):
        """Return a stochastic feature count whose expectation scales with area."""
        interior_area = max(1, (self.width - 2) * (self.height - 2))
        whole, remainder = divmod(interior_area, tiles_per_feature)
        return whole + int(self.rng.random() < remainder / tiles_per_feature)

    def _scaled_linear_feature_count(self, tiles_per_feature):
        """Scale cross-map feature count by map span instead of area."""
        interior_span = math.sqrt(max(1, (self.width - 2) * (self.height - 2)))
        expected_count = interior_span / tiles_per_feature
        whole = int(expected_count)
        return whole + int(self.rng.random() < expected_count - whole)

    def _large_river(self, grid, water, width=3):
        """Draw a broad, relatively straight river from one map side to another."""
        horizontal = self.rng.choice((True, False))
        major_limit = self.width if horizontal else self.height
        minor_limit = self.height if horizontal else self.width
        center = self.rng.randrange(1, minor_limit - 1)
        # Wider rivers get fewer lateral shifts; width 3 is the default broad
        # river and therefore noticeably straighter than a small stream.
        bend_chance = max(0.10, 0.60 / width)
        river_cells = []
        for major in range(1, major_limit - 1):
            if horizontal:
                river_cells.extend(
                    self._carve_river_cross_section(grid, major, center, water, width, horizontal=True)
                )
            else:
                river_cells.extend(
                    self._carve_river_cross_section(grid, center, major, water, width, horizontal=False)
                )
            if self.rng.random() < bend_chance:
                center = min(max(1, center + self.rng.choice((-1, 1))), minor_limit - 2)
        return list(dict.fromkeys(river_cells))

    def _carve_river_cross_section(self, grid, x, y, water, width, horizontal):
        """Carve a clipped perpendicular strip at one point along a river."""
        lower = -(width // 2)
        upper = lower + width
        carved = []
        for offset in range(lower, upper):
            water_x, water_y = (x, y + offset) if horizontal else (x + offset, y)
            if 1 <= water_x < self.width - 1 and 1 <= water_y < self.height - 1:
                cell = grid[water_y][water_x]
                cell.terrain = water
                carved.append(cell)
        return carved

    def _lake_beside_large_river(self, grid, water, river_cells):
        """Grow one 16–28 tile lake directly from an available river bank."""
        bank_cells = [
            neighbor
            for cell in river_cells
            for neighbor in cell.nList
            if neighbor.terrain.passable and neighbor.terrain is not water
        ]
        if not bank_cells:
            return []
        return self._grow_water_patch(
            grid, self.rng.choice(bank_cells), water, self.rng.randint(16, 28),
        )

    def _small_river(self, grid, water, mountain):
        """Draw a one-tile stream that may begin at an edge or in the mountains."""
        mountains = [
            cell for row in grid[1:-1] for cell in row[1:-1]
            if cell.terrain is mountain
        ]
        if mountains and self.rng.random() < 0.60:
            start = self.rng.choice(mountains)
            x, y = start.pos
            delta_x, delta_y = self.rng.choice(
                ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
            )
        else:
            edge = self.rng.choice(("west", "east", "south", "north"))
            if edge == "west":
                x, y, delta_x, delta_y = 1, self.rng.randrange(1, self.height - 1), 1, 0
            elif edge == "east":
                x, y, delta_x, delta_y = self.width - 2, self.rng.randrange(1, self.height - 1), -1, 0
            elif edge == "south":
                x, y, delta_x, delta_y = self.rng.randrange(1, self.width - 1), 1, 0, 1
            else:
                x, y, delta_x, delta_y = self.rng.randrange(1, self.width - 1), self.height - 2, 0, -1

        maximum_length = max(3, min(self.width, self.height) // 2)
        for step in range(maximum_length):
            if not (1 <= x < self.width - 1 and 1 <= y < self.height - 1):
                return
            grid[y][x].terrain = water
            if step and self.rng.random() < 0.25:
                return
            if self.rng.random() < 0.45:
                # Small streams change heading freely, making them windier
                # than broad rivers and able to end in local low ground.
                delta_x, delta_y = self.rng.choice(
                    ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
                )
            x += delta_x
            y += delta_y

    def _grow_water_patch(self, grid, seed, water, tile_count):
        """Flood outward from a seed to make one connected pond or lake."""
        seed.terrain = water
        water_cells = [seed]
        while len(water_cells) < tile_count:
            candidates = [
                neighbor
                for cell in water_cells
                for neighbor in cell.nList
                if neighbor.terrain.passable and neighbor.terrain is not water
            ]
            if not candidates:
                return water_cells
            next_cell = self.rng.choice(candidates)
            next_cell.terrain = water
            water_cells.append(next_cell)
        return water_cells

    def _tunnel_passes(self, grid, road, mountain, tunnel):
        """Turn eligible mountain road passes into tunnels with a 25% chance."""
        conversions = set()
        # Each axis is inspected once, so a road tile between opposite mountain
        # walls has one 25% conversion roll rather than two competing rolls.
        for row in grid[1:-1]:
            for cell in row[1:-1]:
                if cell.terrain is not road:
                    continue
                for delta_x, delta_y in ((1, 0), (0, 1)):
                    forward = grid[cell.pos[1] + delta_y][cell.pos[0] + delta_x]
                    backward = grid[cell.pos[1] - delta_y][cell.pos[0] - delta_x]
                    if forward.terrain is mountain and backward.terrain is mountain:
                        if self.rng.randint(1, 4) == 1:
                            conversions.add(cell)
                    elif {forward.terrain, backward.terrain} == {mountain, road}:
                        if self.rng.randint(1, 4) == 1:
                            # This is a two-wide highway against one mountain
                            # wall; convert both lanes into one tunnel entrance.
                            conversions.add(cell)
                            conversions.add(forward if forward.terrain is road else backward)
        for cell in conversions:
            cell.terrain = tunnel

    def _place_mountain_peak(self, grid, peak, mountain, width):
        """Create a three- to five-tile-wide peak core before adding ridges."""
        lower = -(width // 2)
        upper = lower + width
        for y in range(peak[1] + lower, peak[1] + upper):
            for x in range(peak[0] + lower, peak[0] + upper):
                if 1 <= x < self.width - 1 and 1 <= y < self.height - 1:
                    grid[y][x].terrain = mountain
        # Sparse outer shoulders keep peaks from reading as identical squares.
        shoulder_distance = (width // 2) + 1
        for delta_x, delta_y in (
            (-shoulder_distance, 0),
            (shoulder_distance, 0),
            (0, -shoulder_distance),
            (0, shoulder_distance),
        ):
            x, y = peak[0] + delta_x, peak[1] + delta_y
            if (
                1 <= x < self.width - 1 and 1 <= y < self.height - 1
                and self.rng.randint(1, 100) <= 35
            ):
                grid[y][x].terrain = mountain

    def _ridge_endpoint(self, peak):
        """Choose an in-bounds endpoint three to eight tiles from one peak."""
        for _ in range(20):
            delta_x = self.rng.randint(-8, 8)
            delta_y = self.rng.randint(-8, 8)
            distance = math.hypot(delta_x, delta_y)
            endpoint = [peak[0] + delta_x, peak[1] + delta_y]
            if (
                3 <= distance <= 8
                and 1 <= endpoint[0] < self.width - 1
                and 1 <= endpoint[1] < self.height - 1
            ):
                return endpoint
        return None

    def _draw_mountain_ridge(self, grid, start, end, mountain, width):
        """Draw a two- to five-tile-wide ridge from a peak to its endpoint."""
        steps = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
        horizontal = abs(end[0] - start[0]) >= abs(end[1] - start[1])
        lower = -(width // 2)
        offsets = range(lower, lower + width)
        for step in range(1, steps + 1):
            x = round(start[0] + ((end[0] - start[0]) * step / steps))
            y = round(start[1] + ((end[1] - start[1]) * step / steps))
            for offset in offsets:
                ridge_x, ridge_y = (x, y + offset) if horizontal else (x + offset, y)
                if 1 <= ridge_x < self.width - 1 and 1 <= ridge_y < self.height - 1:
                    grid[ridge_y][ridge_x].terrain = mountain

    def _mountain_edge_forests(self, grid, mountain, forest):
        """Add a sparse tree line around mountain patches without covering rock."""
        changes = []
        for row in grid[1:-1]:
            for cell in row[1:-1]:
                if cell.terrain is not mountain:
                    continue
                for neighbor in cell.nList:
                    if (
                        neighbor.terrain.name == "plains"
                        and self.rng.randint(1, 100) <= 8
                    ):
                        changes.append(neighbor)
        for cell in changes:
            cell.terrain = forest

    def _associate(self, grid, terrain, associated, density, protected_terrain=()):
        multiplier = self._density_multiplier(density)
        protected_terrain = set(protected_terrain)
        for _ in range(multiplier):
            changes = []
            for row in grid[2:-2]:
                for cell in row[2:-2]:
                    neighbors = sum(neighbor.terrain in associated for neighbor in cell.nList)
                    if (
                        cell.terrain not in protected_terrain and cell.terrain not in associated
                        and neighbors and self.rng.randint(1, 100) + neighbors < 5
                    ):
                        changes.append(cell)
            for cell in changes:
                cell.terrain = terrain

    def _roads(self, grid, terrain, density, protected_terrain=()):
        multiplier = self._density_multiplier(density)
        for _ in range(multiplier):
            start, end = self._distant_cells(grid)
            self._draw_road(grid, start, end, terrain, protected_terrain)

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

    def _draw_road(self, grid, start, end, terrain, protected_terrain=()):
        x, y = start
        target_x, target_y = end
        protected_terrain = set(protected_terrain)
        while (x, y) != (target_x, target_y):
            if grid[y][x].terrain not in protected_terrain:
                grid[y][x].terrain = terrain
            if x != target_x and (y == target_y or self.rng.choice((True, False))):
                x += 1 if target_x > x else -1
            elif y != target_y:
                y += 1 if target_y > y else -1
        if grid[target_y][target_x].terrain not in protected_terrain:
            grid[target_y][target_x].terrain = terrain
