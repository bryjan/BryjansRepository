"""Interruptible, energy-aware automatic travel for a player-led squad."""

import heapq
import math


def _route(match, mech, destination):
    """A* prefers economical known terrain; unexplored tiles cost one energy."""
    start = tuple(mech.pos)
    occupied = {tuple(other.pos) for other in match.entities
                if other is not mech and other.team is mech.team}
    frontier = [(0, start)]
    costs, previous = {start: 0}, {}
    while frontier:
        _, cell = heapq.heappop(frontier)
        if cell == destination:
            path = []
            while cell != start:
                path.append(cell)
                cell = previous[cell]
            return list(reversed(path))
        for dx, dy in mech._DIRECTION_OFFSETS.values():
            point = (cell[0] + dx, cell[1] + dy)
            if point in occupied:
                continue
            if not (0 < point[0] < match.mapWidth - 1 and 0 < point[1] < match.mapHeight - 1):
                continue
            terrain = match.map[point[1]][point[0]].terrain
            known = mech.team.mapVisibility.show_all_terrain or point in mech.team.exploredTiles
            if known and (not terrain.passable or terrain.requireFloat and not (mech.flying or mech.mechClass.canFloat or mech.size == 6)):
                continue
            energy = max(0, terrain.moveCost[mech.size]) if known else 1
            if known and energy > mech.mechClass.energyMax:
                continue
            cost = costs[cell] + 1 + energy
            if cost < costs.get(point, float("inf")):
                costs[point], previous[point] = cost, cell
                heuristic = max(abs(point[i] - destination[i]) for i in (0, 1))
                heapq.heappush(frontier, (cost + heuristic, point))
    return []


def advance(match, squad):
    """Take one squad's travel turn, pausing for contact, danger or arrival."""
    from .ai import _can_begin_movement, _energy_floor, _move_follower
    destination = squad.autoTravelTarget
    if destination is None or not squad.mechList:
        return
    leader = squad.squadLead

    def stop(message):
        squad.autoTravelTarget = None
        leader.report(match, message)

    def danger():
        return any(mech.inCombat or mech.trackedEnemies or mech.directlyVisibleEnemies
                   for mech in squad.mechList)

    if danger():
        stop("Automatic travel paused: combat or enemy contact.")
        return
    if math.dist(leader.pos, destination) == 0:
        stop("Automatic travel complete.")
        return
    if not _can_begin_movement(leader, squad.movementMode) and leader.mechClass.energyGen <= 0:
        stop("Automatic travel paused: insufficient power generation to recharge.")
        return
    if _can_begin_movement(leader, squad.movementMode):
        route = _route(match, leader, destination)
        if not route:
            stop("Automatic travel paused: no route found.")
            return
        for position in route:
            energy, reason = leader.moveCostTo(match, position)
            if reason:
                if leader.ap <= 0 or leader.mp <= 0:
                    break
                stop("Automatic travel paused: route blocked or insufficient energy.")
                return
            if leader.energy - energy < _energy_floor(leader, squad.movementMode):
                break
            if any(math.dist(mech.pos, leader.pos) > max(10, leader.visPower) for mech in squad.mechList):
                break
            leader.moveTo(match, position, announce=False)
            leader.getVisuals(match)
            if danger() or leader.destroyed:
                stop("Automatic travel paused: danger detected.")
                return
            if tuple(leader.pos) == destination:
                break
    for mech in list(squad.mechList):
        if mech is not leader:
            _move_follower(match, squad, mech, max(10, leader.visPower), False)
            mech.getVisuals(match)
            if danger():
                stop("Automatic travel paused: enemy contact.")
                return
    if tuple(leader.pos) == destination:
        stop("Automatic travel complete.")
    else:
        # Yield naturally to every other squad, including enemies, and use
        # normal round refresh to replenish movement and energy reserves.
        match.turnEnded = True
