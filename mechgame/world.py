"""Map terrain definitions and procedural world generation."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


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

DEFAULT_MAP_PRESET = "temperate_frontier"
CUSTOM_MAP_PRESET = "custom"

# Mountain dimensions are deliberately large enough to form meaningful areas
# of elevated terrain on the strategic map. Variance scales with each base
# size so a range can still look naturally irregular.
MOUNTAIN_CORE_WIDTH = 6
MOUNTAIN_CORE_VARIANCE = 4
MOUNTAIN_RIDGE_WIDTH = 4
MOUNTAIN_RIDGE_VARIANCE = 16
MOUNTAIN_RIDGE_MIN_LENGTH = 6
MOUNTAIN_RIDGE_MAX_LENGTH = 32


@dataclass(frozen=True)
class MapPreset:
    """Terrain-only parameters for one procedural map style.

    Presets intentionally describe terrain generation only.  Teams, spawn
    positions, objectives, and other scenario content remain the caller's
    responsibility, so this data can serve skirmishes and future scenarios.
    """

    key: str
    name: str
    description: str
    enabled_terrain: frozenset[str]
    forest_density: str
    desert_density: str
    road_density: str
    suburb_density: str
    urban_density: str
    mountain_weight: float = 1
    pond_weight: float = 1
    large_river_weight: float = 1
    small_river_weight: float = 1
    lake_weight: float = 1
    # Route counts are exact per generated map. A highway is two road lanes;
    # an offshoot is a short spur terminating beside a suburb patch.
    highway_count: int = 0
    suburb_offshoot_count: int = 0
    # Adds local expansion passes without increasing the number of forest
    # seeds, so patches grow larger without becoming uniformly dense.
    forest_extra_growth: int = 0
    # Development grows outward from roads and existing districts. Multipliers
    # scale those local growth passes instead of imposing fixed map-size caps.
    suburb_cluster_multiplier: float = 1
    urban_cluster_multiplier: float = 1
    # A spacing value creates an orthogonal road grid. Every third playable
    # row and column yields just over half of the interior as road tiles.
    city_grid_spacing: int | None = None

    def terrain_options(self):
        """Return a fresh toggle dictionary for this preset's terrain."""
        return {
            terrain: terrain in self.enabled_terrain
            for terrain in GENERATABLE_TERRAINS
        }


MAP_PRESETS = (
    MapPreset(
        DEFAULT_MAP_PRESET,
        "Temperate Frontier",
        "Balanced terrain and infrastructure.",
        frozenset(GENERATABLE_TERRAINS),
        forest_density="Thick", desert_density="Light", road_density="Normal",
        suburb_density="Normal", urban_density="Thick", highway_count=1,
        suburb_offshoot_count=1, forest_extra_growth=2,
        suburb_cluster_multiplier=1.25, urban_cluster_multiplier=1.25,
    ),
    MapPreset(
        "badlands",
        "Badlands",
        "Desert, mountains, and sparse roads.",
        frozenset({"desert", "road", "mountain"}),
        forest_density="None", desert_density="Dominant", road_density="Light",
        suburb_density="None", urban_density="None", mountain_weight=1.5,
        pond_weight=0, large_river_weight=0, small_river_weight=0, lake_weight=0,
    ),
    MapPreset(
        "mountain_pass",
        "Mountain Pass",
        "Ridges, forests, streams, and roads.",
        frozenset({"forest", "road", "mountain", "water", "river"}),
        forest_density="Normal", desert_density="None", road_density="Thick",
        suburb_density="None", urban_density="None", mountain_weight=2.5,
        pond_weight=0.5, large_river_weight=0.25, small_river_weight=1.5,
        lake_weight=0.25,
    ),
    MapPreset(
        "river_basin",
        "River Basin",
        "Rivers, lakes, bridges, and towns.",
        frozenset({"forest", "road", "suburb", "urban", "water", "river"}),
        forest_density="Light", desert_density="None", road_density="Thick",
        suburb_density="Normal", urban_density="Normal", mountain_weight=0,
        pond_weight=1.5, large_river_weight=1.5, small_river_weight=2,
        lake_weight=1.5, suburb_cluster_multiplier=1.25,
        urban_cluster_multiplier=1.25,
    ),
    MapPreset(
        "urban_fringe",
        "Super City",
        "A dense street grid with broad urban districts.",
        frozenset({"forest", "road", "suburb", "urban"}),
        forest_density="Light", desert_density="None", road_density="Thick",
        suburb_density="Thick", urban_density="Thick", mountain_weight=0,
        pond_weight=0, large_river_weight=0, small_river_weight=0, lake_weight=0,
        suburb_cluster_multiplier=5, urban_cluster_multiplier=5,
        city_grid_spacing=3,
    ),
    MapPreset(
        "open_steppe",
        "Open Steppe",
        "Open sightlines and sparse rough ground.",
        frozenset({"forest", "desert", "road", "mountain", "water"}),
        forest_density="Light", desert_density="Light", road_density="Normal",
        suburb_density="None", urban_density="None", mountain_weight=0.5,
        pond_weight=0.25, large_river_weight=0, small_river_weight=0, lake_weight=0,
    ),
)
MAP_PRESETS_BY_KEY = {preset.key: preset for preset in MAP_PRESETS}


@dataclass(frozen=True)
class MapRoute:
    """One generated route, stored independently from its terrain tiles."""

    route_id: str
    kind: str
    tiles: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class MapObjective:
    """A scenario-owned objective placed on one or more map tiles."""

    objective_id: str
    name: str
    kind: str
    tiles: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class TacticalLocation:
    """A named area that AI or scenario rules may value strategically."""

    location_id: str
    name: str
    kind: str
    tiles: tuple[tuple[int, int], ...]
    marker_tiles: tuple[tuple[int, int], ...]


@dataclass
class MapFeatures:
    """Derived strategic information attached to a generated map.

    Terrain on ``match.map`` remains authoritative for movement and combat.
    These lists preserve route and scenario intent for patrol AI, objectives,
    and future strategic behavior without repeatedly searching every tile.
    """

    roads: list[MapRoute] = field(default_factory=list)
    rivers: list[MapRoute] = field(default_factory=list)
    bridges: list[tuple[int, int]] = field(default_factory=list)
    objectives: list[MapObjective] = field(default_factory=list)
    tactical_locations: list[TacticalLocation] = field(default_factory=list)

    @staticmethod
    def _coordinates(cells_or_tiles):
        """Normalize Cells or coordinate pairs into immutable map positions."""
        return tuple(tuple(cell.pos) if hasattr(cell, "pos") else tuple(cell) for cell in cells_or_tiles)

    def add_road(self, kind, cells_or_tiles):
        """Register one patrol-capable route in its generation order."""
        tiles = self._coordinates(cells_or_tiles)
        if tiles:
            self.roads.append(MapRoute(f"road_{len(self.roads) + 1}", kind, tiles))

    def add_river(self, kind, cells_or_tiles):
        """Register one watercourse separately from lakes and ponds."""
        tiles = self._coordinates(cells_or_tiles)
        if tiles:
            self.rivers.append(MapRoute(f"river_{len(self.rivers) + 1}", kind, tiles))

    def add_objective(self, objective_id, name, kind, cells_or_tiles):
        """Add scenario content without coupling it to terrain generation."""
        self.objectives.append(
            MapObjective(objective_id, name, kind, self._coordinates(cells_or_tiles))
        )

    def add_tactical_location(self, location_id, name, kind, cells_or_tiles,
                              marker_tiles=None):
        """Add an AI area, optionally using a smaller set of debug markers."""
        tiles = self._coordinates(cells_or_tiles)
        markers = tiles if marker_tiles is None else self._coordinates(marker_tiles)
        self.tactical_locations.append(
            TacticalLocation(location_id, name, kind, tiles, markers)
        )

    def refresh_bridges(self):
        """Record road/river overlaps after procedural route generation ends."""
        road_tiles = {tile for route in self.roads for tile in route.tiles}
        river_tiles = {tile for route in self.rivers for tile in route.tiles}
        self.bridges = sorted(road_tiles & river_tiles)


def get_map_preset(key):
    """Return one named terrain profile or explain the available choices."""
    try:
        return MAP_PRESETS_BY_KEY[key]
    except KeyError as error:
        valid = ", ".join(preset.key for preset in MAP_PRESETS)
        raise ValueError(f"Unknown map preset {key!r}; choose one of: {valid}.") from error


class MapGenerator:
    """Builds a map and attaches its terrain catalogue to a match.

    `match` is intentionally duck-typed here so world generation remains
    independent from match flow and combat rules.
    """

    DENSITY_MULTIPLIERS = {
        "None": 0,
        "Light": 1,
        "Normal": 2,
        "Thick": 3,
        # Used for terrain that defines a map's identity rather than merely
        # decorating it. The Badlands desert must dominate open plains.
        "Dominant": 12,
    }

    def __init__(
        self, width: int, height: int | random.Random | None = None,
        rng: random.Random | None = None, terrain_enabled=None,
        map_preset=DEFAULT_MAP_PRESET,
    ):
        # Preserve ``MapGenerator(size, rng)`` while also allowing rectangles.
        if isinstance(height, random.Random):
            rng = height
            height = None
        self.width = width
        self.height = width if height is None else height
        self.rng = rng if rng is not None else random.Random()
        self.map_preset_id = DEFAULT_MAP_PRESET if map_preset is None else map_preset
        # Custom maps retain the familiar Temperate Frontier frequencies while
        # letting the player choose every individual terrain toggle.
        preset_key = (
            DEFAULT_MAP_PRESET
            if map_preset in (None, CUSTOM_MAP_PRESET)
            else map_preset
        )
        self.map_preset = get_map_preset(preset_key)
        self.terrain_enabled = self._terrain_options(terrain_enabled)
        self.features = MapFeatures()
        if self.width < 8 or self.height < 8:
            raise ValueError("Maps must be at least 8 tiles wide and 8 tiles high.")

    def _terrain_options(self, overrides):
        """Merge optional terrain toggles while rejecting misspelled tile IDs."""
        defaults = self.map_preset.terrain_options()
        if overrides is None:
            return defaults
        unknown = set(overrides) - set(GENERATABLE_TERRAINS)
        if unknown:
            raise ValueError(f"Unknown terrain toggle(s): {', '.join(sorted(unknown))}")
        return {
            terrain: bool(overrides.get(terrain, enabled))
            for terrain, enabled in defaults.items()
        }

    def build(self, match):
        # Delayed import avoids a cycle while the legacy domain module is being
        # transitioned into smaller modules.
        from .terrain import Cell, TerrainType

        self.features = MapFeatures()
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
            self._scatter(
                grid,
                terrain["forest"],
                self.map_preset.forest_density,
                protected_terrain,
                extra_growth=self.map_preset.forest_extra_growth,
            )
            if self.terrain_enabled["mountain"]:
                self._mountain_edge_forests(grid, terrain["mountain"], terrain["forest"])
        if self.terrain_enabled["desert"]:
            self._scatter(
                grid, terrain["desert"], self.map_preset.desert_density, protected_terrain,
            )
        if self.terrain_enabled["road"]:
            protected_terrain = self._build_road_network(
                grid, terrain, protected_terrain,
            )
        if self.terrain_enabled["suburb"]:
            suburb_neighbors = [terrain["suburb"]]
            if self.terrain_enabled["road"]:
                suburb_neighbors.append(terrain["road"])
            self._associate(
                grid,
                terrain["suburb"],
                suburb_neighbors,
                self.map_preset.suburb_density,
                protected_terrain,
                cluster_multiplier=self.map_preset.suburb_cluster_multiplier,
            )
        # Urban centers form dense pockets around developed road corridors,
        # rather than appearing as isolated buildings across open terrain.
        if self.terrain_enabled["urban"]:
            urban_neighbors = [terrain["urban"]]
            if self.terrain_enabled["road"]:
                urban_neighbors.append(terrain["road"])
            if self.terrain_enabled["suburb"]:
                urban_neighbors.append(terrain["suburb"])
            # A terrain combination can leave no road or suburb tiles (for
            # example, when a mountain pass converts a short road entirely to
            # tunnel). Seed a district whenever no valid urban anchor exists.
            has_urban_anchor = any(
                cell.terrain in urban_neighbors
                for row in grid[1:-1] for cell in row[1:-1]
            )
            if not has_urban_anchor:
                self._seed_urban_district(
                    grid, terrain["urban"], urban_neighbors, protected_terrain,
                )
            self._associate(
                grid,
                terrain["urban"],
                urban_neighbors,
                self.map_preset.urban_density,
                protected_terrain,
                cluster_multiplier=self.map_preset.urban_cluster_multiplier,
            )
            if not any(
                cell.terrain is terrain["urban"]
                for row in grid[1:-1] for cell in row[1:-1]
            ):
                self._seed_urban_district(
                    grid, terrain["urban"], urban_neighbors, protected_terrain,
                )
        self.features.refresh_bridges()
        self._identify_terrain_locations(grid, terrain)
        match.mapFeatures = self.features
        return grid

    def _identify_terrain_locations(self, grid, terrain):
        """Register inexpensive, terrain-defined strategic areas.

        These are facts about the generated board, not scenario objectives.
        Scenario setup can later choose suitable entries from this registry as
        objective, reinforcement, or patrol anchors.
        """
        # A wide river crossing can occupy several tiles. It is one tactical
        # bridge area, so the overview gets one central marker rather than a
        # row of markers that can read as a road running beside the river.
        for index, tiles in enumerate(self._connected_position_groups(self.features.bridges), start=1):
            self.features.add_tactical_location(
                f"bridge_{index}",
                f"Bridge {index}",
                "bridge",
                tiles,
                marker_tiles=[self._central_tile(tiles)],
            )

        for index, tiles in enumerate(self._road_intersections(), start=1):
            self.features.add_tactical_location(
                f"road_intersection_{index}",
                f"Road Intersection {index}",
                "road_intersection",
                tiles,
            )

        for index, tiles in enumerate(self._mountain_road_entrances(grid, terrain["mountain"]), start=1):
            self.features.add_tactical_location(
                f"mountain_entrance_{index}",
                f"Mountain Road Entrance {index}",
                "mountain_entrance",
                tiles,
            )

    @staticmethod
    def _central_tile(tiles):
        """Choose a stable representative tile for a compact area marker."""
        center_x = sum(x for x, _ in tiles) / len(tiles)
        center_y = sum(y for _, y in tiles) / len(tiles)
        return min(
            tiles,
            key=lambda tile: ((tile[0] - center_x) ** 2) + ((tile[1] - center_y) ** 2),
        )

    def _mountain_road_entrances(self, grid, mountain):
        """Find road route tiles where a route first meets mountain terrain."""
        road_tiles = {tile for route in self.features.roads for tile in route.tiles}

        def touches_mountain(position):
            x, y = position
            return any(
                0 <= x + delta_x < self.width
                and 0 <= y + delta_y < self.height
                and grid[y + delta_y][x + delta_x].terrain is mountain
                for delta_x, delta_y in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )

        entrances = {
            position
            for position in road_tiles
            if touches_mountain(position)
            and any(
                neighbor in road_tiles and not touches_mountain(neighbor)
                for neighbor in self._cardinal_positions(position)
            )
        }
        return self._connected_position_groups(entrances)

    def _road_intersections(self):
        """Find shared route tiles without mistaking parallel highway lanes for junctions."""
        route_counts = {}
        for route in self.features.roads:
            for position in set(route.tiles):
                route_counts[position] = route_counts.get(position, 0) + 1
        intersections = {
            position for position, route_count in route_counts.items()
            if route_count >= 2
        }
        return self._connected_position_groups(intersections)

    @staticmethod
    def _cardinal_positions(position):
        """Yield the four immediately adjacent coordinates for route checks."""
        x, y = position
        return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))

    def _connected_position_groups(self, positions):
        """Group adjacent tactical tiles into deterministic named-area inputs."""
        remaining = set(positions)
        groups = []
        while remaining:
            frontier = [remaining.pop()]
            group = []
            while frontier:
                position = frontier.pop()
                group.append(position)
                for neighbor in self._cardinal_positions(position):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        frontier.append(neighbor)
            groups.append(tuple(sorted(group)))
        return sorted(groups)

    def _seed_urban_district(self, grid, urban, anchors, protected_terrain):
        """Place one guaranteed urban seed when random growth found none."""
        protected = set(protected_terrain)
        cells = [
            cell for row in grid[1:-1] for cell in row[1:-1]
            if cell.terrain in anchors and cell.terrain not in protected
        ]
        if not cells:
            cells = [
                cell for row in grid[1:-1] for cell in row[1:-1]
                if cell.terrain.passable and cell.terrain not in protected
            ]
        if cells:
            self.rng.choice(cells).terrain = urban

    def _scatter(self, grid, terrain, density, protected_terrain=(), extra_growth=0):
        """Seed and expand terrain patches, optionally favoring larger patches."""
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
        for _ in range(multiplier + extra_growth):
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
        """Place large peak cores with one to two irregular long ridges."""
        range_count = max(
            1,
            self._scaled_feature_count(2500, self.map_preset.mountain_weight),
        )
        for _ in range(range_count):
            # Keep the peak and each ridge independently irregular.  A range
            # can therefore have a compact core with a broad ridge, or the
            # reverse, instead of all of its features sharing one width.
            peak_width = MOUNTAIN_CORE_WIDTH + self.rng.randint(
                0, MOUNTAIN_CORE_VARIANCE,
            )
            peak = self._mountain_peak_location(peak_width)
            self._place_mountain_peak(grid, peak, mountain, peak_width)
            for _ in range(self.rng.randint(1, 2)):
                ridge_end = self._ridge_endpoint(peak)
                if ridge_end is not None:
                    ridge_length = math.dist(peak, ridge_end)
                    maximum_width = min(
                        MOUNTAIN_RIDGE_WIDTH + MOUNTAIN_RIDGE_VARIANCE,
                        math.ceil(ridge_length) - 1,
                    )
                    self._draw_mountain_ridge(
                        grid,
                        peak,
                        ridge_end,
                        mountain,
                        self.rng.randint(MOUNTAIN_RIDGE_WIDTH, maximum_width),
                    )

    def _still_water(self, grid, water):
        """Generate sparse connected ponds.

        Rivers and their bank-side lakes are generated separately so lakes can
        be tied to a meaningful waterway rather than appearing at random.
        """
        # A water-enabled profile gets at least one small pond. This keeps
        # compact maps tactically interesting while still scaling large-map
        # pond counts through the profile's weight.
        pond_count = max(
            1,
            self._scaled_feature_count(1600, self.map_preset.pond_weight),
        ) if self.map_preset.pond_weight > 0 else 0
        for _ in range(pond_count):
            candidates = [
                cell for row in grid[1:-1] for cell in row[1:-1]
                if cell.terrain is not water
            ]
            if not candidates:
                return
            self._grow_water_patch(
                grid, self.rng.choice(candidates), water, self.rng.randint(3, 6),
            )

    def _rivers(self, grid, water, mountain):
        """Add winding streams and scalable edge-to-edge large rivers."""
        # Broad rivers cross the full map, so their density must scale with
        # map span rather than raw area. A roughly 100×100 map gets one; much
        # larger maps can still receive more without a fixed global cap.
        large_river_count = self._scaled_linear_feature_count(
            100, self.map_preset.large_river_weight,
        )
        large_river_cells = []
        for _ in range(large_river_count):
            river_cells = self._large_river(grid, water, width=3)
            large_river_cells.extend(river_cells)
            self.features.add_river("large_river", river_cells)
        # Lake attempts retain the requested area-scaled rate, but cannot
        # exceed the number of broad rivers available to feed them.
        lake_count = min(
            large_river_count,
            self._scaled_feature_count(1000, self.map_preset.lake_weight),
        )
        for _ in range(lake_count):
            self._lake_beside_large_river(grid, water, large_river_cells)
        # Small tributary-like streams are deliberately less common. They may
        # begin in mountain terrain or enter from an edge, then end naturally.
        small_river_count = self._scaled_linear_feature_count(
            50, self.map_preset.small_river_weight,
        )
        for _ in range(small_river_count):
            self.features.add_river("small_river", self._small_river(grid, water, mountain))

    def _scaled_feature_count(self, tiles_per_feature, weight=1):
        """Return an area-scaled feature count adjusted by a preset weight."""
        if weight <= 0:
            return 0
        interior_area = max(1, (self.width - 2) * (self.height - 2))
        expected_count = (interior_area / tiles_per_feature) * weight
        whole = int(expected_count)
        remainder = expected_count - whole
        return whole + int(self.rng.random() < remainder)

    def _scaled_linear_feature_count(self, tiles_per_feature, weight=1):
        """Scale cross-map feature count by span and a preset feature weight."""
        if weight <= 0:
            return 0
        interior_span = math.sqrt(max(1, (self.width - 2) * (self.height - 2)))
        expected_count = (interior_span / tiles_per_feature) * weight
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
        tile_count = self.rng.randint(16, 28)
        spacious_banks = [
            cell for cell in bank_cells
            if self._passable_patch_capacity(cell, water, tile_count) >= tile_count
        ]
        if not spacious_banks:
            return []
        return self._grow_water_patch(
            grid, self.rng.choice(spacious_banks), water, tile_count,
        )

    @staticmethod
    def _passable_patch_capacity(seed, water, limit):
        """Count reachable non-water cells, stopping once a patch can fit."""
        visited = {id(seed)}
        frontier = [seed]
        while frontier and len(visited) < limit:
            cell = frontier.pop()
            for neighbor in cell.nList:
                if (
                    id(neighbor) not in visited
                    and neighbor.terrain.passable
                    and neighbor.terrain is not water
                ):
                    visited.add(id(neighbor))
                    frontier.append(neighbor)
                    if len(visited) >= limit:
                        break
        return len(visited)

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
        river_cells = []
        for step in range(maximum_length):
            if not (1 <= x < self.width - 1 and 1 <= y < self.height - 1):
                return river_cells
            cell = grid[y][x]
            cell.terrain = water
            river_cells.append(cell)
            if step and self.rng.random() < 0.25:
                return river_cells
            if self.rng.random() < 0.45:
                # Small streams change heading freely, making them windier
                # than broad rivers and able to end in local low ground.
                delta_x, delta_y = self.rng.choice(
                    ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
                )
            x += delta_x
            y += delta_y
        return river_cells

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

    def _mountain_peak_location(self, core_width):
        """Choose a peak position with room for its full core."""
        negative_radius = core_width // 2
        positive_radius = core_width - negative_radius - 1
        return [
            self.rng.randint(1 + negative_radius, self.width - 2 - positive_radius),
            self.rng.randint(1 + negative_radius, self.height - 2 - positive_radius),
        ]

    def _place_mountain_peak(self, grid, peak, mountain, width):
        """Create a six- to ten-tile-wide peak core before adding ridges."""
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
        """Choose an in-bounds endpoint six to thirty-two tiles from one peak."""
        for _ in range(20):
            delta_x = self.rng.randint(
                -MOUNTAIN_RIDGE_MAX_LENGTH, MOUNTAIN_RIDGE_MAX_LENGTH,
            )
            delta_y = self.rng.randint(
                -MOUNTAIN_RIDGE_MAX_LENGTH, MOUNTAIN_RIDGE_MAX_LENGTH,
            )
            distance = math.hypot(delta_x, delta_y)
            endpoint = [peak[0] + delta_x, peak[1] + delta_y]
            if (
                MOUNTAIN_RIDGE_MIN_LENGTH <= distance <= MOUNTAIN_RIDGE_MAX_LENGTH
                and 1 <= endpoint[0] < self.width - 1
                and 1 <= endpoint[1] < self.height - 1
            ):
                return endpoint
        return None

    def _draw_mountain_ridge(self, grid, start, end, mountain, width):
        """Draw a four- to twenty-tile-wide ridge from a peak to its endpoint."""
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

    def _associate(self, grid, terrain, associated, density, protected_terrain=(),
                   cluster_multiplier=1):
        """Grow clustered terrain around its anchors with scalable intensity."""
        multiplier = math.ceil(self._density_multiplier(density) * cluster_multiplier)
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
        """Draw each road across opposite playable edges of the map."""
        multiplier = self._density_multiplier(density)
        for _ in range(multiplier):
            start, end = self._road_endpoints()
            road_cells = self._draw_road(grid, start, end, terrain, protected_terrain)
            self.features.add_road("road", road_cells)

    def _build_road_network(self, grid, terrain, protected_terrain):
        """Create ordinary roads, highways, and suburb spurs for one preset."""
        road = terrain["road"]
        if self.map_preset.city_grid_spacing is None:
            self._roads(grid, road, self.map_preset.road_density)
        else:
            self._city_grid_roads(
                grid, road, self.map_preset.city_grid_spacing, protected_terrain,
            )
        self._highways(grid, road, self.map_preset.highway_count)
        if self.terrain_enabled["suburb"]:
            self._road_offshoots(
                grid,
                road,
                terrain["suburb"],
                self.map_preset.suburb_offshoot_count,
                protected_terrain,
            )
        if not self.terrain_enabled["mountain"]:
            return protected_terrain

        self._tunnel_passes(grid, road, terrain["mountain"], terrain["tunnel"])
        return (*protected_terrain, terrain["tunnel"])

    def _city_grid_roads(self, grid, road, spacing, protected_terrain=()):
        """Lay an evenly spaced road grid that scales with playable map span."""
        protected = set(protected_terrain)
        for y in range(1, self.height - 1, spacing):
            route = []
            for x in range(1, self.width - 1):
                cell = grid[y][x]
                if cell.terrain not in protected:
                    cell.terrain = road
                    route.append(cell)
            self.features.add_road("city_grid_horizontal", route)
        for x in range(1, self.width - 1, spacing):
            route = []
            for y in range(1, self.height - 1):
                cell = grid[y][x]
                if cell.terrain not in protected:
                    cell.terrain = road
                    route.append(cell)
            self.features.add_road("city_grid_vertical", route)

    def _highways(self, grid, terrain, count):
        """Draw two-lane edge-to-edge highways alongside ordinary roads."""
        for _ in range(count):
            start, end = self._road_endpoints()
            path = self._draw_road(grid, start, end, terrain)
            horizontal = abs(end[0] - start[0]) >= abs(end[1] - start[1])
            lanes = []
            for cell in path:
                if horizontal:
                    lane_x = cell.pos[0]
                    lane_y = cell.pos[1] + (1 if cell.pos[1] < self.height - 2 else -1)
                else:
                    lane_x = cell.pos[0] + (1 if cell.pos[0] < self.width - 2 else -1)
                    lane_y = cell.pos[1]
                grid[lane_y][lane_x].terrain = terrain
                lanes.append(grid[lane_y][lane_x])
            self.features.add_road("highway", [*path, *lanes])

    def _road_offshoots(self, grid, road, suburb, count, protected_terrain):
        """Add short road spurs that terminate beside small suburb patches."""
        protected = set(protected_terrain)
        for _ in range(count):
            road_cells = [
                cell for row in grid[2:-2] for cell in row[2:-2]
                if cell.terrain is road
            ]
            if not road_cells:
                return
            start = self.rng.choice(road_cells)
            endpoint = self._offshoot_endpoint(grid, start, protected)
            if endpoint is None:
                continue
            road_cells = self._draw_road(grid, start.pos, endpoint.pos, road, protected)
            self.features.add_road("offshoot", road_cells)
            self._grow_suburb_patch(grid, endpoint, suburb, protected)

    def _offshoot_endpoint(self, grid, start, protected):
        """Find a short cardinal branch that ends on clear, passable ground."""
        directions = ((1, 0), (-1, 0), (0, 1), (0, -1))
        for _ in range(12):
            delta_x, delta_y = self.rng.choice(directions)
            distance = self.rng.randint(4, 8)
            end_x = start.pos[0] + (delta_x * distance)
            end_y = start.pos[1] + (delta_y * distance)
            if not (2 <= end_x < self.width - 2 and 2 <= end_y < self.height - 2):
                continue
            path_is_clear = all(
                grid[start.pos[1] + (delta_y * step)][start.pos[0] + (delta_x * step)].terrain
                not in protected
                for step in range(1, distance + 1)
            )
            if not path_is_clear:
                continue
            endpoint = grid[end_y][end_x]
            if endpoint.terrain.passable and endpoint.terrain not in protected:
                return endpoint
        return None

    def _grow_suburb_patch(self, grid, endpoint, suburb, protected):
        """Place a 6–12 tile suburb patch adjacent to a road offshoot endpoint."""
        candidates = [
            cell for cell in endpoint.nList
            if (
                cell.terrain.passable
                and cell.terrain not in protected
                and cell.terrain.name not in {"road", "tunnel"}
            )
        ]
        if not candidates:
            return
        seed = self.rng.choice(candidates)
        seed.terrain = suburb
        patch = [seed]
        target_size = self.rng.randint(6, 12)
        while len(patch) < target_size:
            candidates = [
                neighbor
                for cell in patch
                for neighbor in cell.nList
                if (
                    neighbor.terrain.passable
                    and neighbor.terrain not in protected
                    and neighbor.terrain is not suburb
                    and neighbor.terrain.name not in {"road", "tunnel"}
                )
            ]
            if not candidates:
                return
            next_cell = self.rng.choice(candidates)
            next_cell.terrain = suburb
            patch.append(next_cell)

    def _density_multiplier(self, density):
        """Translate a readable map-density setting into a generation count."""
        try:
            return self.DENSITY_MULTIPLIERS[density]
        except KeyError as error:
            valid = ", ".join(self.DENSITY_MULTIPLIERS)
            raise ValueError(f"Unknown density {density!r}; choose one of: {valid}.") from error

    def _road_endpoints(self):
        """Return endpoints on two opposite interior edges of the map border."""
        if self.rng.choice((True, False)):
            return (
                [1, self.rng.randrange(1, self.height - 1)],
                [self.width - 2, self.rng.randrange(1, self.height - 1)],
            )
        return (
            [self.rng.randrange(1, self.width - 1), 1],
            [self.rng.randrange(1, self.width - 1), self.height - 2],
        )

    def _draw_road(self, grid, start, end, terrain, protected_terrain=()):
        x, y = start
        target_x, target_y = end
        protected_terrain = set(protected_terrain)
        road_cells = []
        while (x, y) != (target_x, target_y):
            if grid[y][x].terrain not in protected_terrain:
                grid[y][x].terrain = terrain
                road_cells.append(grid[y][x])
            if x != target_x and (y == target_y or self.rng.choice((True, False))):
                x += 1 if target_x > x else -1
            elif y != target_y:
                y += 1 if target_y > y else -1
        if grid[target_y][target_x].terrain not in protected_terrain:
            grid[target_y][target_x].terrain = terrain
            road_cells.append(grid[target_y][target_x])
        return road_cells
