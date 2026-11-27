"""Raid Military Base debug scenario, deployment and objective lifecycle."""

from dataclasses import dataclass, field
import math
import heapq

from .ai import SquadGoal, TeamGoal, start_road_patrol
from .patrols import recorded_road_walk
from .stamps import MilitaryBaseStamp
from .world import MapGenerator

BASE_DEFENSE_RADIUS = 20
BASE_DEFENSE_PRIORITY = 150  # Initial patrol/hold orders use 100.
ATTACK_GOALS = {"attack", "attack_military_base", "eliminate_enemies"}


def _defense_order_key(goal):
    """Raid order categories take precedence over caller-supplied numbers."""
    rank = 2 if goal.kind in ATTACK_GOALS else 1 if goal.kind == "return_to_defend" else 0
    return (-rank, -goal.priority, goal.goal_id)


@dataclass
class RaidObjective:
    player: object
    defender: object
    base_tiles: frozenset
    held_since: dict = field(default_factory=dict)
    raided: bool = False
    title: str = "Raid Military Base"
    defense_alert: bool = False

    def update_defense(self, match, team):
        """Recall the garrison after a shared visual sighting near the base.

        The alarm stays active after contact is lost. Return/defend outranks
        patrol, while committed attacks and emergency withdrawal still run.
        Radar-only contacts and unseen enemy positions never raise the alarm.
        """
        if team is not self.defender:
            return
        if not self.defense_alert:
            self.defense_alert = any(
                mech.team is self.player and tuple(mech.pos) in team.sharedVisibleTiles
                and min(math.dist(mech.pos, point) for point in self.base_tiles) <= BASE_DEFENSE_RADIUS
                for mech in match.entities
            )
            if not self.defense_alert:
                return
            team.reportLog.append(["Raid defense alarm: attackers spotted near the base. "
                                   "Return and defend after higher-priority attacks.", True, False])
            order = TeamGoal("raid_defense_alarm", "return_to_defend", BASE_DEFENSE_PRIORITY,
                             tuple(sorted(self.base_tiles)),
                             "Attackers visually confirmed near the base: recall all garrisons after attack orders.",
                             objective_id="raid_base")
            team.currentGoals.append(order)
            team.currentGoals.sort(key=_defense_order_key)
            team.currentGoal = team.currentGoals[0]
            team.goalHistory.append(order)
        for index, squad in enumerate(team.squadsList):
            if squad.playerControlled or not squad.mechList:
                continue
            goal_id = f"raid_recall_{index}"
            recall = next((goal for goal in squad.currentGoals if goal.goal_id == goal_id), None)
            if recall is None:
                recall = SquadGoal(goal_id, "raid_defense_alarm", "return_to_defend", BASE_DEFENSE_PRIORITY,
                                   tuple(sorted(self.base_tiles)),
                                   "Attackers spotted near the objective: return and defend the base. "
                                   "Complete higher-priority attack orders first.", objective_id="raid_base")
                squad.currentGoals.append(recall)
                squad.goalHistory.append(recall)
                squad.logAI(match, "Order received: return and defend base; above patrol, below attack.")
            # Attack is a higher order category even if its caller supplied a
            # lower numeric priority. Retain the recall in the pending queue.
            squad.currentGoals.sort(key=_defense_order_key)
            previous = squad.currentGoal
            squad.currentGoal = squad.currentGoals[0]
            if squad.currentGoal.kind == "return_to_defend" and previous is not squad.currentGoal:
                squad.stopRoadPatrol()
                squad.investigationPosition = None
                squad.setMovementPolicy(mode="move", behavior="formation")
                attacking = (squad.combatPosture == "attack"
                             or squad.combinedAttack is not None
                             or squad.ambushTriggered)
                if not attacking:
                    squad.ambushLocation = None
                    squad.ambushGroup = ()
                    squad.primaryTarget = None
                    for mech in squad.mechList:
                        mech.approachTarget = mech.approachWeapon = None
            squad._refreshOperationalFlags()

    def status(self, match=None):
        if self.raided:
            return "Raid complete: extract or clear enemies."
        if self.held_since:
            return "Holding base: survive the enemy response until the next friendly round."
        if match is not None and self.occupants(match):
            return "Inside objective base: end a squad turn to begin the hold."
        return "Enter the marked base and hold for one turn."

    def occupants(self, match):
        """Return live friendly mechs inside this objective's exact footprint."""
        return [mech for mech in match.entities if mech.team is self.player
                and not mech.destroyed and tuple(mech.pos) in self.base_tiles]

    def _refresh_holds(self, match):
        present = set(self.occupants(match))
        for mech in list(self.held_since):
            if mech not in present:
                self.held_since.pop(mech)
        return present

    def end_turn(self, match, squad):
        """Record team occupancy even if the player switched squads before end."""
        if squad.team is self.player and not self.raided:
            for mech in self._refresh_holds(match):
                self.held_since.setdefault(mech, match.matchRound)

    def begin_turn(self, match, squad):
        """Complete after the enemy response, independently of the current POV."""
        if self.raided:
            return
        self._refresh_holds(match)
        if squad.team is self.player:
            for mech, start_round in self.held_since.items():
                if match.matchRound <= start_round:
                    continue
                self.raided = True
                mech.report(match, "Base raid complete! Extract surviving mechs or clear the enemy from the map.", critical=True)
                break

    def moved(self, mech):
        if tuple(mech.pos) not in self.base_tiles:
            self.held_since.pop(mech, None)

    def finish_if_decided(self, match):
        """Extraction requires at least one intact return; elimination alone loses."""
        players = any(s.mechList for s in self.player.squadsList)
        enemies = any(s.mechList for s in self.defender.squadsList)
        extracted = any(mech.team is self.player for mech in match.fledMechs)
        success = self.raided and ((not players and extracted) or not enemies)
        if players and enemies:
            return False
        match.matchOver = True
        match.winner = self.player if success else self.defender
        match.resultMessage = f"{self.title}: " + (
            "SUCCESS — base raided and force extracted or enemy cleared."
            if success else "FAILED — raid objective not completed before the battle ended."
        )
        match.turnEnded = match.advTurn = False
        match.resolvePilotSurvival()
        return True


def ensure_land_access(match, start, goals):
    """Preserve natural routes; bridge the minimum water only if it blocks access."""
    start, goals = tuple(start), set(goals)
    costs, previous = {start: (0, 0)}, {}
    frontier = [(0, 0, start)]
    while frontier:
        water, steps, point = heapq.heappop(frontier)
        if costs[point] != (water, steps):
            continue
        if point in goals:
            route = []
            while point != start:
                route.append(point)
                point = previous[point]
            bridges, segment = [], []
            for x, y in reversed(route):
                cell = match.map[y][x]
                if cell.terrain.requireFloat:
                    cell.terrain = match.road
                    segment.append(cell)
                elif segment:
                    bridges.append(segment)
                    segment = []
            if segment:
                bridges.append(segment)
            for bridge in bridges:
                match.mapFeatures.add_road("raid_bridge", bridge)
                match.mapFeatures.add_tactical_location(
                    f"raid_bridge_{len(match.mapFeatures.roads)}", "River crossing", "bridge",
                    bridge, marker_tiles=[bridge[0], bridge[-1]],
                )
            match.mapFeatures.refresh_bridges()
            return
        x, y = point
        for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
            candidate = (x + dx, y + dy)
            if not (0 < candidate[0] < match.mapWidth - 1 and 0 < candidate[1] < match.mapHeight - 1):
                continue
            tile = match.map[candidate[1]][candidate[0]].terrain
            if not tile.passable:
                continue
            cost = (water + int(tile.requireFloat), steps + 1)
            if cost < costs.get(candidate, (float("inf"), float("inf"))):
                costs[candidate], previous[candidate] = cost, point
                heapq.heappush(frontier, (*cost, candidate))
    raise ValueError("Raid deployment has no traversable route to the base.")


def _deploy_road_patrol(match, squad):
    """Start patrols on local roads instead of marooning them in mountains.

    Reserve rules intentionally prevent sustained mountain travel by light
    patrols. Give them a usable road deployment rather than flattening a path
    through generated terrain or relaxing those reserve rules.
    """
    occupied = {tuple(mech.pos) for mech in match.entities if mech.squad is not squad}
    covered = {tile for other in squad.team.squadsList if other is not squad for tile in other.patrolRoute}
    candidates = []
    from .radar import entity_detection_threshold
    for road in match.mapFeatures.roads:
        route = recorded_road_walk(match, road, squad.squadLead.pos)
        positions = []
        for point in sorted(set(route), key=lambda point: (math.dist(point, squad.squadLead.pos), point)):
            if point in occupied:
                continue
            if match.map[point[1]][point[0]].terrain.name not in {"road", "tunnel"}:
                continue
            if any(math.dist(point, previous) < 3 for previous in positions):
                continue
            mech = squad.mechList[len(positions)]
            # Retain the scenario's hidden-entry guarantee when choosing
            # road positions, including the guard's possible sensor burst.
            if any(math.dist(point, enemy.pos) <= max(
                    mech.visPower * 1.4,
                    (mech.mechClass.radarPower * 1.4 - entity_detection_threshold(enemy.radarSig)) / 2)
                   for enemy in match.entities if enemy.team is not squad.team):
                continue
            positions.append(point)
            if len(positions) == len(squad.mechList):
                break
        if len(positions) == len(squad.mechList):
            # Prefer a route that leaves the compound over a short perimeter
            # circuit, even when both patrols must share part of a main road.
            span = max(max(p[axis] for p in route) - min(p[axis] for p in route) for axis in (0, 1))
            overlap = len(set(route) & covered) / len(set(route))
            candidates.append((span < 20,
                               math.dist(positions[0], squad.squadLead.pos) + 12 * overlap,
                               road.route_id, positions))
    if not candidates:
        # Generated base access normally provides a route; keep the regular
        # planner fallback for custom generators without usable local roads.
        return start_road_patrol(match, squad)
    _, _, route_id, positions = min(candidates)
    for mech, position in zip(squad.mechList, positions):
        mech.pos = list(position)
        mech.turnStartPos = list(position)
    return start_road_patrol(match, squad, route_id)


def setup(match):
    """Place a guaranteed edge base and separated forces on a random map."""
    player, defender = match.teamList
    # Work in an entry-to-base coordinate frame, then rotate/reflect it onto
    # any map edge. Both lateral positions and distance from the edges vary.
    edge = match.rng.randrange(4)
    span_u = match.mapWidth if edge < 2 else match.mapHeight
    span_v = match.mapHeight if edge < 2 else match.mapWidth

    def project(u, v):
        if edge == 0:
            return (u, v)
        if edge == 1:
            return (match.mapWidth - 1 - u, v)
        if edge == 2:
            return (v, u)
        return (v, match.mapHeight - 1 - u)

    base_u = match.rng.randint(span_u - 26, span_u - 14)
    base_v = match.rng.randint(18, span_v - 26)
    entry_v = match.rng.randint(15, span_v - 16)
    corners = [project(base_u, base_v), project(base_u + 7, base_v + 7)]
    origin = (min(point[0] for point in corners), min(point[1] for point in corners))
    player_anchors = [(match.rng.randint(4, 9), entry_v - 6),
                      (match.rng.randint(4, 9), entry_v + 6)]
    defender_anchors = [(base_u + 4 + match.rng.randint(-2, 2),
                         base_v + 4 + (index - 1) * 10 + match.rng.randint(-1, 1))
                        for index in range(len(defender.squadsList))]
    # Keep one garrison on the objective itself. The other squads cover its
    # approaches on repeating patrols rather than all holding their spawn.
    defender_anchors[0] = (base_u + 4, base_v + 4)
    defender_anchors[1] = (base_u + 4, base_v - 10)
    stamp = MilitaryBaseStamp(8, 8)
    footprint = set(stamp.positions(origin))
    match.mapFeatures.military_bases = [base for base in match.mapFeatures.military_bases
                                        if not footprint.intersection(base.tiles)]
    # Scenario content may replace a small footprint of generated terrain.
    # The rest of the map and its random tactical features remain intact.
    for x, y in stamp.positions(origin):
        match.map[y][x].terrain = match.plains
    generator = MapGenerator(match.mapWidth, height=match.mapHeight, rng=match.rng)
    generator.features = match.mapFeatures
    base = generator.add_military_base(match.map, match.road, match.suburb, origin=origin, stamp=stamp)
    if base is None:
        raise ValueError("Could not place the raid base.")
    center = project(base_u + 4, base_v + 4)
    # Clear a compact entry zone so neither player squad starts isolated in
    # a pond or behind an impassable patch, regardless of the chosen preset.
    for v in range(entry_v - 10, entry_v + 11):
        for u in range(1, 13):
            x, y = project(u, v)
            match.map[y][x].terrain = match.plains
    # Do not lay a road from the player's deployment to the objective. Keep
    # a natural land approach, adding only an essential water crossing.
    ensure_land_access(match, project(6, entry_v), base.tiles)
    match.mapFeatures.add_objective("raid_base", "Raid Military Base", "raid_military_base", base.tiles)
    match.mapFeatures.add_tactical_location("raid_base_approach", "Base entrance", "base_entrance", (project(base_u, base_v + 4),))
    occupied = set()
    for side, team in enumerate((player, defender)):
        for index, squad in enumerate(team.squadsList):
            anchor = player_anchors[index] if side == 0 else defender_anchors[index]
            positions = [project(anchor[0] + dx, anchor[1] + dy)
                         for dx, dy in ((0, 0), (-3, -3), (3, 3), (-3, 3), (3, -3))]
            for mech, position in zip(squad.mechList, positions):
                if position in occupied:
                    raise ValueError("Raid deployment overlaps another unit.")
                occupied.add(position)
                match.map[position[1]][position[0]].terrain = match.plains
                mech.pos = list(position)
                mech.turnStartPos = list(position)
                match.entities.append(mech)
    defender.mapVisibility.show_all_terrain = True
    defender.mapVisibility.show_all_objectives = True
    player.mapVisibility.show_all_objectives = True
    match.playerSquad = player.squadsList[0]
    match.pov = match.playerSquad.squadLead
    match.raidObjective = RaidObjective(player, defender, frozenset(base.tiles))
    for index, squad in enumerate(defender.squadsList):
        holding = index == 0
        kind = "defend_location" if holding else "patrol_location"
        message = ("Hold the base with visual coverage of the objective." if holding
                   else "Patrol roads serving the base and its approaches; repeat until contact.")
        goal = SquadGoal(f"raid_defense_{index}", "raid_defense", kind, 100,
                         (center,), message, objective_id="raid_base")
        squad.currentGoal = goal
        squad.currentGoals = [goal]
        squad.goalHistory.append(goal)
        squad.refreshCombatForce()
        if not holding:
            # Allocate sequentially so route scoring avoids the other patrol's
            # coverage. Ordinary combat and retreat logic may interrupt it.
            _deploy_road_patrol(match, squad)
    # Validate final deployments after patrols have joined their roads.
    from .radar import entity_detection_threshold
    for guard in defender.squadsList:
        for enemy in guard.mechList:
            for squad in player.squadsList:
                for mech in squad.mechList:
                    distance = math.dist(enemy.pos, mech.pos)
                    radar_range = max(0, (enemy.mechClass.radarPower * 1.4 - entity_detection_threshold(mech.radarSig)) / 2)
                    if distance <= max(enemy.visPower * 1.4, radar_range):
                        raise ValueError("Raid deployment would expose player mechs at the start.")
    for squad in player.squadsList:
        squad.squadLead.report(match,
            f"Raid Military Base: yellow 'R' at {list(center)}. End a turn inside and hold through the enemy response. "
            "Then extract all surviving mechs using 'flee', or clear all enemies. "
            "Use 'sq' to switch squads; 'm' opens the map and debug controls. 'quit' returns to the test menu.",
            critical=True)
