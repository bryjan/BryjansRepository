"""Bounded catch-up routing for followers separated from their squad leader."""

import heapq
import math

MAX_CATCHUP_SEARCH = 2500


def catchup_route(match, squad, mech, leader_range):
    """Find an economical route back into a spaced formation around the SL.

    Unlike a greedy step, a route may temporarily move sideways or away to
    get around a wall. Unknown terrain is estimated as plains; actual moves
    still use the shared movement validation and energy reserve rules.
    """
    from .ai import FORMATION_SPACING
    start = tuple(mech.pos)
    leader = squad.squadLead
    teammates = [other.pos for other in squad.mechList if other is not mech]
    known_enemies = set([*mech.directlyVisibleEnemies, *mech.trackedEnemies])
    occupied = {tuple(other.pos) for other in match.entities if other is not mech
                and (other.team is mech.team or other in known_enemies)}
    costs, previous = {start: 0}, {}
    frontier = [(0, start)]
    expanded = set()
    while frontier and len(expanded) < MAX_CATCHUP_SEARCH:
        _, point = heapq.heappop(frontier)
        if point in expanded:
            continue
        expanded.add(point)
        if (math.dist(point, leader.pos) <= leader_range
                and all(math.dist(point, other) >= FORMATION_SPACING for other in teammates)):
            route = []
            while point != start:
                route.append(list(point))
                point = previous[point]
            return list(reversed(route))
        for dx, dy in mech._DIRECTION_OFFSETS.values():
            candidate = (point[0] + dx, point[1] + dy)
            if candidate in occupied or not (0 < candidate[0] < match.mapWidth - 1 and 0 < candidate[1] < match.mapHeight - 1):
                continue
            terrain = match.map[candidate[1]][candidate[0]].terrain
            known = mech.team.mapVisibility.show_all_terrain or candidate in mech.team.exploredTiles
            if known:
                if not terrain.passable or terrain.requireFloat and not (mech.mechClass.canFloat or mech.flying or mech.size == 6):
                    continue
                energy = terrain.moveCost[mech.size]
                if mech.flying:
                    energy = max(energy, mech.size)
                if energy > mech.mechClass.energyMax:
                    continue
            else:
                energy = 1
            cost = costs[point] + 1 + max(0, energy)
            if cost < costs.get(candidate, float("inf")):
                previous[candidate] = point
                costs[candidate] = cost
                heuristic = max(0, math.dist(candidate, leader.pos) - leader_range) / math.sqrt(2)
                heapq.heappush(frontier, (cost + heuristic, candidate))
    return []
