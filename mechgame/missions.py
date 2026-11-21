"""Scenario mission templates that create map content and team objectives."""

from .world import MapGenerator

__all__ = ["MissionGenerator"]


class MissionGenerator:
    """Build mission objectives after terrain generation has completed."""

    def __init__(self, match_info):
        self.match = match_info

    def _next_id(self, kind):
        self.match._nextMissionId += 1
        return f"{kind}_{self.match._nextMissionId}"

    @staticmethod
    def _locations(location):
        """Accept one coordinate, Cells, or a recorded strategic area."""
        if hasattr(location, "tiles"):
            return tuple(location.tiles)
        if hasattr(location, "pos"):
            return (tuple(location.pos),)
        if len(location) == 2 and all(isinstance(value, int) for value in location):
            return (tuple(location),)
        return tuple(tuple(entry.pos) if hasattr(entry, "pos") else tuple(entry) for entry in location)

    def _issue(self, team, kind, name, locations, priority, message, required_roles):
        """Register a map objective and hand its matching order to one team."""
        mission_id = self._next_id(kind)
        locations = tuple(locations)
        self.match.mapFeatures.add_objective(mission_id, name, kind, locations)
        goal = self.match.issueTeamObjective(
            team,
            kind,
            priority,
            locations,
            message,
            required_roles=required_roles,
            objective_id=mission_id,
            goal_id=f"mission_{mission_id}",
        )
        self.match.missions.append(goal)
        return goal

    def _ensure_military_base(self):
        """Return a base, adding one with normal terrain rules if necessary."""
        if self.match.mapFeatures.military_bases:
            return self.match.mapFeatures.military_bases[0]

        generator = MapGenerator(
            self.match.mapWidth,
            height=self.match.mapHeight,
            rng=self.match.rng,
        )
        generator.features = self.match.mapFeatures
        protected_terrain = (
            self.match.border,
            self.match.water,
            self.match.mountain,
            self.match.urban,
        )
        base = generator.add_military_base(
            self.match.map,
            self.match.road,
            self.match.suburb,
            protected_terrain,
        )
        if base is None:
            raise ValueError("No valid terrain remains for a mission military base.")
        return base

    def add_pilot_recovery(self, team, location, pilot_name="Missing Pilot", priority=70):
        """Create a recovery beacon objective for scout-capable squads."""
        locations = self._locations(location)
        return self._issue(
            team, "pilot_recovery", f"Recover {pilot_name}", locations, priority,
            f"Recover {pilot_name} from the marked location.", ("sensor", "scout"),
        )

    def add_recover_or_steal_mech(self, team, location, mech_name="Disabled Mech", priority=75):
        """Create a mission to retrieve, capture, or deny an unattended mech.

        TODO(retrieval): place a recoverable mech entity or wreck at the
        objective and define interaction, towing, ownership transfer, and
        pilot-rescue rules. For now this is intentionally a strategic order
        only, so it does not grant a free combat unit.
        """
        locations = self._locations(location)
        return self._issue(
            team, "recover_or_steal_mech", f"Recover or Steal {mech_name}",
            locations, priority,
            f"Recover, capture, or deny {mech_name} at the marked location.",
            ("front_line", "skirmisher"),
        )

    def add_attack_military_base(self, team, priority=70):
        """Create an assault mission against an existing or newly stamped base."""
        base = self._ensure_military_base()
        return self._issue(
            team, "attack_military_base", f"Attack {base.base_id}", base.tiles, priority,
            "Attack and secure the military base.", ("front_line", "artillery"),
        )

    def add_map_patrol(self, team, priority=30):
        """Create a long patrol using the map's longest recorded road route."""
        routes = [route for route in self.match.mapFeatures.roads if route.tiles]
        if routes:
            route = max(routes, key=lambda candidate: len(candidate.tiles))
            indices = sorted({0, len(route.tiles) // 2, len(route.tiles) - 1})
            locations = tuple(route.tiles[index] for index in indices)
        else:
            locations = ((self.match.mapWidth // 2, self.match.mapHeight // 2),)
        return self._issue(
            team, "patrol_map", "Map Patrol", locations, priority,
            "Patrol the assigned route and investigate threats.", ("sensor", "skirmisher"),
        )

    def add_patrol_near_location(self, team, location, priority=40):
        """Create a local patrol around one tactical location or coordinate."""
        locations = self._locations(location)
        return self._issue(
            team, "patrol_location", "Local Patrol", locations, priority,
            "Patrol and secure the assigned area.", ("sensor", "skirmisher"),
        )

    def add_defend_location(self, team, location, priority=80):
        """Create a static defense order for a base, objective, or coordinate."""
        locations = self._locations(location)
        return self._issue(
            team, "defend_location", "Defend Location", locations, priority,
            "Defend the assigned location against enemy forces.", ("front_line", "anchor"),
        )
