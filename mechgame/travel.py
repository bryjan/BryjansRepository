"""Player-led automatic formation movement and travel warnings."""

from collections import deque
import math


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
        if mech is not leader and math.dist(mech.pos, leader.pos) > max(10, leader.visPower):
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
    from .ai import _can_begin_movement, _legal_steps
    if not _can_begin_movement(mech, squad.movementMode):
        return []
    moved = []
    while True:
        on_road = tuple(mech.pos) in roads
        if on_road and roads[tuple(mech.pos)] <= 2:
            break
        join = min(roads, key=lambda point: (math.dist(mech.pos, point), roads[point]))
        options = []
        for position, energy in _legal_steps(match, mech, squad.movementMode):
            point = tuple(position)
            if on_road:
                if point not in roads or roads[point] >= roads[tuple(mech.pos)]:
                    continue
                score = roads[point]
            else:
                if math.dist(position, join) >= math.dist(mech.pos, join):
                    continue
                score = math.dist(position, join)
            options.append((score, energy, position))
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
    """After a manual SL move, run one normal AI follower pass in this turn."""
    from .ai import _is_roadway, _move_follower
    if not squad.autoTravelEnabled or not squad.playerControlled or not squad.mechList:
        return []
    leader = squad.squadLead
    roads = _road_distances(match, leader) if _is_roadway(match, leader.pos) else None
    moved = []
    for mech in list(squad.mechList):
        if mech is leader:
            continue
        mech.approachTarget = mech.approachWeapon = None
        steps = (_follow_road(match, squad, mech, roads) if roads is not None else
                 _move_follower(match, squad, mech, max(10, leader.visPower), False))
        moved.extend(steps)
        if steps and not mech.destroyed:
            mech.getVisuals(match)
    warnings(match, squad)
    return moved
