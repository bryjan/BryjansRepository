"""Player-led automatic formation movement and travel warnings."""

from collections import deque
import math

from .formation import formation_radius


def warnings(match, squad):
    """Report threshold crossings once until the problem has cleared."""
    leader = squad.squadLead
    if leader is None:
        return
    current = set()
    for mech in squad.mechList:
        problems = []
        if mech.energy < mech.mechClass.energyMax * .5:
            problems.append(("energy", "Travel warning: energy below 50%."))
        if mech is not leader and math.dist(mech.pos, leader.pos) > formation_radius(leader):
            problems.append(("lag", "Travel warning: lagging beyond the squad leader's formation range."))
        for kind, message in problems:
            key = (mech, kind)
            current.add(key)
            if key not in squad.travelWarnings:
                mech.report(match, message, critical=True)
                print(f"Warning — {mech.pilot.display_name}: {message}")
    squad.travelWarnings = current


def _road_distances(match, leader):
    """Map the road component connected to the leader, including tunnels."""
    from .ai import _is_roadway
    start = tuple(leader.pos)
    distances = {start: 0}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in leader._DIRECTION_OFFSETS.values():
            point = (x + dx, y + dy)
            if point in distances or not (0 < point[0] < match.mapWidth - 1 and 0 < point[1] < match.mapHeight - 1):
                continue
            if _is_roadway(match, point):
                distances[point] = distances[(x, y)] + 1
                queue.append(point)
    return distances


def _follow_road(match, squad, mech, roads):
    """Join the leader's road and follow it without minimum squad spacing."""
    from .ai import _can_begin_movement, _energy_floor, _legal_steps
    from .formation import road_approach_route
    if not _can_begin_movement(mech, squad.movementMode):
        return []
    moved = []
    if tuple(mech.pos) not in roads:
        # A direct step toward the nearest road can be blocked by a wall or
        # riverbank. Use the same bounded detour search as AI road patrols.
        route = road_approach_route(
            match, mech, roads,
            mech.mechClass.energyMax - _energy_floor(mech, squad.movementMode),
        )
        for position in route:
            energy, reason = mech.moveCostTo(match, position)
            if reason or mech.energy - energy < _energy_floor(mech, squad.movementMode):
                break
            if not mech.moveTo(match, position, announce=False):
                break
            moved.append(mech)
            if mech.destroyed:
                return moved
        if tuple(mech.pos) not in roads:
            return moved
    while True:
        distance = roads[tuple(mech.pos)]
        if distance <= 2:
            break
        options = []
        for position, energy in _legal_steps(match, mech, squad.movementMode):
            point = tuple(position)
            if point in roads and roads[point] < distance:
                options.append((roads[point], energy, position))
        if not options:
            break
        _, _, position = min(options)
        if not mech.moveTo(match, position, announce=False):
            break
        moved.append(mech)
        if mech.destroyed:
            break
    return moved


def follow(match, squad):
    """Use available follower actions after SL movement, waiting or ending turn."""
    from .ai import _is_roadway, _move_follower
    if not squad.autoTravelEnabled or not squad.playerControlled or not squad.mechList:
        return []
    leader = squad.squadLead
    roads = _road_distances(match, leader) if _is_roadway(match, leader.pos) else None
    moved = []
    followers = [mech for mech in squad.mechList if mech is not leader]
    # Clear the front of a road column before moving the units behind it.
    # Roster order is command order and need not match physical formation.
    followers.sort(key=lambda mech: roads.get(tuple(mech.pos), float("inf"))
                   if roads is not None else math.dist(mech.pos, leader.pos))
    for mech in followers:
        mech.approachTarget = mech.approachWeapon = None
    # A teammate may vacate a needed cell later in the pass. Retry after real
    # progress; AP consumption bounds this loop and blocked squads stop once.
    while True:
        progress = []
        for mech in followers:
            if mech.destroyed or mech not in squad.mechList:
                continue
            steps = (_follow_road(match, squad, mech, roads) if roads is not None else
                     _move_follower(match, squad, mech, formation_radius(leader), False))
            progress.extend(steps)
            if steps and not mech.destroyed:
                mech.getVisuals(match)
        if not progress:
            break
        moved.extend(progress)
    warnings(match, squad)
    return moved
