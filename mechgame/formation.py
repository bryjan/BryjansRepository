"""Terrain-aware routes for squad movement, regrouping and joining patrol roads."""

import heapq
import math
from collections import deque

MAX_CATCHUP_SEARCH = 2500
MAX_DESTINATION_SEARCH = 20000
MAX_LEADER_DISTANCE = 10
MAX_TEAMMATE_DISTANCE = 5


def formation_radius(leader):
    """Use a fixed formation tether, independent of sensor range or boosts."""
    return MAX_LEADER_DISTANCE


def _step_energy(match, mech, point):
    """Estimate known terrain faithfully; undiscovered ground stays neutral."""
    known = mech.team.mapVisibility.show_all_terrain or point in mech.team.exploredTiles
    if not known:
        return 1
    terrain = match.map[point[1]][point[0]].terrain
    if not terrain.passable or terrain.requireFloat and not (mech.mechClass.canFloat or mech.flying or mech.size == 6):
        return None
    energy = terrain.moveCost[mech.size]
    return max(energy, mech.size) if mech.flying else energy


def formation_area(match, mech, leader_range):
    """Nearby formation cells must connect to the SL by traversable terrain.

    Straight-line proximity across a river is not a valid formation. This
    small flood fill is bounded by the ten-tile tether and ignores temporary
    unit occupancy; execution still validates every step normally.
    """
    from .ai import _energy_floor
    leader = mech.squad.squadLead
    start = tuple(leader.pos)
    area, queue = {start}, deque([(start, 0)])
    budget = mech.mechClass.energyMax - _energy_floor(mech, mech.squad.movementMode)
    while queue:
        point, distance = queue.popleft()
        if distance >= leader_range:
            continue
        for dx, dy in mech._DIRECTION_OFFSETS.values():
            candidate = (point[0] + dx, point[1] + dy)
            if candidate in area or not (0 < candidate[0] < match.mapWidth - 1 and 0 < candidate[1] < match.mapHeight - 1):
                continue
            if math.dist(candidate, start) > leader_range:
                continue
            energy = _step_energy(match, mech, candidate)
            if energy is None or energy > budget:
                continue
            area.add(candidate)
            queue.append((candidate, distance + 1))
    return area


def catchup_route(match, squad, mech, leader_range, area=None):
    """Find an economical route back into a spaced formation around the SL.

    Unlike a greedy step, a route may temporarily move sideways or away to
    get around a wall. Unknown terrain is estimated as plains; actual moves
    still use the shared movement validation and energy reserve rules.
    """
    from .ai import FORMATION_SPACING, _energy_floor
    leader = squad.squadLead
    area = formation_area(match, mech, leader_range) if area is None else area
    teammates = [other.pos for other in squad.mechList if other is not mech]
    return _find_route(
        match, mech,
        lambda point: (point in area
                       and min(math.dist(point, other) for other in teammates) <= MAX_TEAMMATE_DISTANCE
                       and all(math.dist(point, other) >= FORMATION_SPACING for other in teammates)),
        lambda point: max(0, math.dist(point, leader.pos) - leader_range) / math.sqrt(2),
        max_step_energy=mech.mechClass.energyMax - _energy_floor(mech, squad.movementMode),
        search_limit=MAX_DESTINATION_SEARCH,
    )


def road_approach_route(match, mech, road_tiles, max_step_energy):
    """Join the assigned patrol road without getting trapped by a land obstacle."""
    goals = set(road_tiles)
    if not goals:
        return []
    return _find_route(match, mech, lambda point: point in goals,
                       lambda point: min(math.dist(point, goal) for goal in goals) / math.sqrt(2),
                       max_step_energy)


def destination_route(match, mech, destination, max_step_energy):
    """Find an economical move-order route, including detours to bridges.

    A friendly-occupied destination can be approached from an adjacent cell.
    The route uses the same terrain knowledge and movement limits as catch-up.
    """
    destination = tuple(destination)
    occupied = any(other is not mech and tuple(other.pos) == destination
                   and other.team is mech.team for other in match.entities)
    radius = math.sqrt(2) if occupied else 0
    return _find_route(
        match, mech, lambda point: math.dist(point, destination) <= radius,
        lambda point: max(0, math.dist(point, destination) - radius) / math.sqrt(2),
        max_step_energy,
        search_limit=MAX_DESTINATION_SEARCH,
    )


def _find_route(match, mech, reached, heuristic, max_step_energy=None, search_limit=MAX_CATCHUP_SEARCH):
    """Share bounded, knowledge-limited routing between formation and patrols."""
    start = tuple(mech.pos)
    known_enemies = set([*mech.directlyVisibleEnemies, *mech.trackedEnemies])
    occupied = {tuple(other.pos) for other in match.entities if other is not mech
                and (other.team is mech.team or other in known_enemies)}
    costs, previous = {start: 0}, {}
    frontier = [(0, start)]
    expanded = set()
    while frontier and len(expanded) < search_limit:
        _, point = heapq.heappop(frontier)
        if point in expanded:
            continue
        expanded.add(point)
        if reached(point):
            route = []
            while point != start:
                route.append(list(point))
                point = previous[point]
            return list(reversed(route))
        for dx, dy in mech._DIRECTION_OFFSETS.values():
            candidate = (point[0] + dx, point[1] + dy)
            if candidate in occupied or not (0 < candidate[0] < match.mapWidth - 1 and 0 < candidate[1] < match.mapHeight - 1):
                continue
            energy = _step_energy(match, mech, candidate)
            if energy is None or energy > mech.mechClass.energyMax:
                continue
            if max_step_energy is not None and energy > max_step_energy:
                continue
            cost = costs[point] + 1 + max(0, energy)
            if cost < costs.get(candidate, float("inf")):
                previous[candidate] = point
                costs[candidate] = cost
                heapq.heappush(frontier, (cost + heuristic(candidate), candidate))
    return []
