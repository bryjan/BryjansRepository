"""Strategic objective assignment and visibility-limited squad movement.

This module validates and distributes objectives, then executes a bounded
first movement pass. It never reads hidden enemy or map information, leaving
combat choices for the future squad-leader action planner.
"""

from dataclasses import dataclass
import math

__all__ = [
    "SquadGoal", "TeamGoal", "assign_team_goals", "assign_team_goals_to_squads",
    "execute_squad_combat", "execute_squad_movement", "issue_team_goal",
    "start_road_patrol",
]


FORMATION_SPACING = 3
MIN_LEADER_VISUAL_RANGE = 10
# Patrols favor roads serving strategic terrain and their assigned objective,
# while treating another friendly patrol's recorded road as a meaningful cost.
PATROL_TACTICAL_RADIUS = 10
PATROL_OBJECTIVE_RADIUS = 16
PATROL_TACTICAL_WEIGHT = 5
PATROL_OBJECTIVE_WEIGHT = 6
PATROL_OVERLAP_PENALTY = 12
# A one-tile shoulder lets opposing or converging patrols pass on a narrow
# road without letting a patrol drift into ordinary off-road movement.
ROAD_PATROL_WIGGLE_RADIUS = 1
AI_FIRE_ACCURACY_THRESHOLD = 65
AI_APPROACH_ACCURACY_THRESHOLD = 80
AI_GOOD_AMMO_THRESHOLD = .50
ENERGY_RESERVE_BANDS = {
    # A patrol may take a costly catch-up step, but it only begins a burst
    # near full charge and stops before falling below its sustainable reserve.
    "patrol": (.85, .95),
    "move": (.70, .90),
    "double_time": (.20, .50),
}
_ADJACENT_OFFSETS = (
    (-1, -1), (0, -1), (1, -1), (-1, 0),
    (1, 0), (-1, 1), (0, 1), (1, 1),
)


@dataclass(frozen=True)
class TeamGoal:
    """One match-issued strategic objective for a team.

    ``locations`` stores immutable coordinates instead of mutable Cells.
    ``required_roles`` records the capabilities a squad should bring; it is an
    eligibility hint for the forthcoming team-planning layer, not a constraint
    on player-controlled squads.
    """

    goal_id: str
    kind: str
    priority: int
    locations: tuple[tuple[int, int], ...] = ()
    message: str = ""
    required_roles: tuple[str, ...] = ()
    objective_id: str | None = None

    @property
    def target_tiles(self):
        """Compatibility name for callers that predate multi-location goals."""
        return self.locations

    @property
    def description(self):
        """Compatibility name for the player/AI-facing objective message."""
        return self.message


@dataclass(frozen=True)
class SquadGoal:
    """A team objective tailored and handed down to one non-player squad."""

    goal_id: str
    team_goal_id: str
    kind: str
    priority: int
    locations: tuple[tuple[int, int], ...] = ()
    message: str = ""
    required_roles: tuple[str, ...] = ()
    objective_id: str | None = None

    @property
    def target_tiles(self):
        """Compatibility name shared with TeamGoal."""
        return self.locations


def _coordinates(locations):
    """Normalize one coordinate or a collection of Cells into immutable pairs."""
    if locations is None:
        return ()
    if hasattr(locations, "pos"):
        locations = (locations,)
    else:
        locations = tuple(locations)
        if len(locations) == 2 and all(isinstance(value, int) for value in locations):
            locations = (locations,)

    coordinates = []
    for location in locations:
        coordinate = tuple(location.pos) if hasattr(location, "pos") else tuple(location)
        if len(coordinate) != 2 or not all(isinstance(value, int) for value in coordinate):
            raise ValueError("Goal locations must be map coordinates or Cells.")
        coordinates.append(coordinate)
    return tuple(coordinates)


def _install_goals(team, goals, replace=False):
    """Store a priority-sorted objective queue and preserve the active alias."""
    existing = [] if replace else list(team.currentGoals)
    new_ids = {goal.goal_id for goal in goals}
    existing = [goal for goal in existing if goal.goal_id not in new_ids]
    team.currentGoals = sorted(
        [*existing, *goals], key=lambda goal: (-goal.priority, goal.goal_id),
    )
    team.currentGoal = team.currentGoals[0] if team.currentGoals else None
    team.goalHistory.extend(goals)


def _install_squad_goals(squad, goals, replace=False):
    """Store one squad's priority-sorted orders and preserve its active alias."""
    existing = [] if replace else list(squad.currentGoals)
    new_ids = {goal.goal_id for goal in goals}
    existing = [goal for goal in existing if goal.goal_id not in new_ids]
    squad.currentGoals = sorted(
        [*existing, *goals], key=lambda goal: (-goal.priority, goal.goal_id),
    )
    squad.currentGoal = squad.currentGoals[0] if squad.currentGoals else None
    squad.goalHistory.extend(goals)
    squad._refreshOperationalFlags()


def _next_goal_id(match_info):
    """Create a deterministic per-match identifier for ad-hoc objectives."""
    match_info._nextTeamGoalId += 1
    return f"goal_{match_info._nextTeamGoalId}"


def issue_team_goal(match_info, team, kind, priority, locations=(), message="",
                    required_roles=(), objective_id=None, goal_id=None):
    """Hand one team a new or replacement objective during a live match."""
    if team not in match_info.teamList:
        raise ValueError("Goals can only be issued to a team in this match.")
    if priority < 0:
        raise ValueError("Goal priority cannot be negative.")

    goal = TeamGoal(
        goal_id=goal_id or _next_goal_id(match_info),
        kind=kind,
        priority=priority,
        locations=_coordinates(locations),
        message=message,
        required_roles=tuple(dict.fromkeys(required_roles)),
        objective_id=objective_id,
    )
    _install_goals(team, [goal])
    return goal


def _squad_role_readiness(squad, required_roles):
    """Return the weakest required capability supplied anywhere in a squad."""
    if not required_roles:
        return 100
    readiness = squad.roleReadiness()
    return min(readiness.get(role, 0) for role in required_roles)


def assign_team_goals_to_squads(team):
    """Hand each team order to the best capable non-player squad.

    A squad can fulfill separate required roles with different mechs, which is
    why readiness is evaluated across the squad rather than only on its lead.
    This only records orders; the later squad-leader layer decides routes and
    individual actions.

    TODO(ai-team-planner): balance simultaneous objectives across eligible
    squads instead of allowing the best squad to inherit several orders.
    """
    ai_squads = [squad for squad in team.squadsList if not squad.playerControlled]
    team_goal_ids = {goal.goal_id for goal in team.currentGoals}
    for squad in ai_squads:
        # Replace stale hand-downs while preserving future local-only orders.
        squad.currentGoals = sorted(
            (
                goal for goal in squad.currentGoals
                if goal.team_goal_id in team_goal_ids
            ),
            key=lambda goal: (-goal.priority, goal.goal_id),
        )
        squad.currentGoal = squad.currentGoals[0] if squad.currentGoals else None
        squad._refreshOperationalFlags()

    for team_goal in team.currentGoals:
        candidates = [
            squad for squad in ai_squads
            if squad.mechList and squad.canFillRoles(team_goal.required_roles)
        ]
        if not candidates:
            continue
        squad = max(
            candidates,
            key=lambda candidate: (
                _squad_role_readiness(candidate, team_goal.required_roles),
                candidate.combatEffective,
                candidate.combatForce,
                len(candidate.mechList),
            ),
        )
        squad_index = team.squadsList.index(squad) + 1
        squad_goal = SquadGoal(
            goal_id=f"{team_goal.goal_id}:squad_{squad_index}",
            team_goal_id=team_goal.goal_id,
            kind=team_goal.kind,
            priority=team_goal.priority,
            locations=team_goal.locations,
            message=team_goal.message,
            required_roles=team_goal.required_roles,
            objective_id=team_goal.objective_id,
        )
        _install_squad_goals(squad, [squad_goal])


def _goal_for_objective(objective):
    """Translate one scenario objective into the neutral default team order."""
    return TeamGoal(
        goal_id=f"objective_{objective.objective_id}",
        kind="secure_objective",
        priority=100,
        locations=objective.tiles,
        message=f"Secure {objective.name}.",
        objective_id=objective.objective_id,
    )


def assign_team_goals(match_info):
    """Give every team one starting objective after scenario setup is complete.

    Scenario objectives take precedence. Until scenarios define ownership or
    asymmetric objective rules, every team receives the same neutral order to
    secure the first declared objective. Objective-free skirmishes keep a
    low-priority elimination fallback so later match events can supersede it.
    """
    objective = next(iter(match_info.mapFeatures.objectives), None)
    for team in match_info.teamList:
        goal = _goal_for_objective(objective) if objective else TeamGoal(
            goal_id="eliminate_enemies",
            kind="eliminate_enemies",
            priority=1,
            message="Eliminate all opposing operational mechs.",
        )
        _install_goals(team, [goal], replace=True)
        assign_team_goals_to_squads(team)


# ---------------------------------------------------------------------------
# First-pass AI movement
# ---------------------------------------------------------------------------

def _nearest_location(origin, locations):
    """Return the closest location, retaining deterministic coordinate ties."""
    return min(locations, key=lambda location: (math.dist(origin, location), location))


def _leader_destination(match_info, squad):
    """Choose a known, legal-information destination for the squad leader."""
    leader = squad.squadLead
    patrol_destination = (
        _patrol_destination(match_info, squad, leader)
        if _road_patrol_active(squad) else None
    )
    if patrol_destination is not None:
        return patrol_destination
    target = squad.primaryTarget
    if _attack_ordered(squad) and target in match_info.entities and not target.destroyed:
        return target.pos
    if squad.currentGoal and squad.currentGoal.locations:
        return _nearest_location(leader.pos, squad.currentGoal.locations)
    # Direct sight and radar tracking are both already filtered by the normal
    # sensing system. Do not inspect arbitrary enemies in the match here.
    contacts = [*leader.directlyVisibleEnemies, *leader.trackedEnemies]
    if contacts:
        return _nearest_location(leader.pos, [contact.pos for contact in contacts])
    if squad.currentGoal and squad.currentGoal.kind == "eliminate_enemies":
        # This neutral search point is map knowledge, not hidden enemy data.
        # TODO(ai-search): replace it with unexplored-frontier scouting once
        # the planner can assess map coverage rather than just route patrols.
        return (match_info.mapWidth // 2, match_info.mapHeight // 2)
    return None


def _is_roadway(match_info, position):
    """Return whether a position uses road-style movement for a patrol."""
    terrain = match_info.map[position[1]][position[0]].terrain
    return terrain.name in {"road", "tunnel"}


def _road_patrol_active(squad):
    """Recognize an explicit road patrol or an AI-issued patrol objective."""
    goal_kind = getattr(squad.currentGoal, "kind", "")
    return squad.movementBehavior == "road_patrol" or goal_kind in {
        "patrol", "patrol_map", "patrol_location", "defend",
    }


def _recorded_road_tiles(match_info, route):
    """Keep only still-usable tiles from one generated and recorded route."""
    tiles = []
    for tile in route.tiles:
        if _is_roadway(match_info, tile) and (not tiles or tiles[-1] != tile):
            tiles.append(tile)
    return tuple(tiles)


def _route_distance(route_tiles, locations):
    """Return the nearest Euclidean distance between one route and locations."""
    return min(
        math.dist(route_tile, location)
        for route_tile in route_tiles
        for location in locations
    )


def _other_patrol_tiles(squad):
    """Return friendly patrol coverage the leader should avoid duplicating."""
    if not getattr(squad, "team", None):
        return set()
    return {
        tile
        for other_squad in squad.team.squadsList
        if other_squad is not squad
        for tile in other_squad.patrolRoute
    }


def _patrol_route_score(match_info, squad, route_tiles):
    """Score one route using strategic value, objective access, and coverage."""
    tactical_score = sum(
        max(0, PATROL_TACTICAL_RADIUS - _route_distance(route_tiles, location.tiles))
        * PATROL_TACTICAL_WEIGHT
        for location in match_info.mapFeatures.tactical_locations
        if location.tiles
    )
    objective_tiles = getattr(squad.currentGoal, "locations", ())
    objective_score = 0
    if objective_tiles:
        objective_score = max(
            0, PATROL_OBJECTIVE_RADIUS - _route_distance(route_tiles, objective_tiles),
        ) * PATROL_OBJECTIVE_WEIGHT
    overlap = len(set(route_tiles) & _other_patrol_tiles(squad))
    return tactical_score + objective_score - (overlap * PATROL_OVERLAP_PENALTY)


def start_road_patrol(match_info, squad, route_id=None):
    """Give a squad leader a repeatable patrol order from recorded map roads.

    A selected route is stored on the squad rather than reconstructed from raw
    terrain each turn.  Patrol and defense AI may call this helper because
    map features are neutral scenario knowledge, not hidden enemy data.
    """
    routes = getattr(match_info.mapFeatures, "roads", ())
    candidates = [
        (route, _recorded_road_tiles(match_info, route))
        for route in routes
        if route_id is None or route.route_id == route_id
    ]
    candidates = [candidate for candidate in candidates if len(candidate[1]) >= 2]
    if not candidates:
        return False

    origin = squad.squadLead.pos
    ranked_routes = sorted(
        candidates,
        key=lambda candidate: (
            -_patrol_route_score(match_info, squad, candidate[1]),
            _route_distance(candidate[1], (tuple(origin),)),
            candidate[0].route_id,
        ),
    )
    route, tiles = ranked_routes[0]
    squad.beginRoadPatrol(route.route_id, tiles)
    return True


def _ensure_road_patrol(match_info, squad):
    """Create a default route for patrol/defense orders only when needed."""
    if squad.patrolRoute:
        return True
    goal_kind = getattr(squad.currentGoal, "kind", "")
    if squad.movementBehavior == "road_patrol" or goal_kind in {
        "patrol", "patrol_map", "patrol_location", "defend",
    }:
        return start_road_patrol(match_info, squad)
    return False


def _patrol_destination(match_info, squad, leader):
    """Return and advance toward the next ordered road waypoint.

    Non-circuit routes reverse at their endpoints.  This makes a simple road
    repeat indefinitely without fabricating a route through unknown terrain.
    """
    route = squad.patrolRoute
    if not route:
        return None
    index = squad.patrolRouteIndex

    def advance(index):
        next_index = index + squad.patrolRouteDirection
        if not 0 <= next_index < len(route):
            squad.patrolRouteDirection *= -1
            next_index = index + squad.patrolRouteDirection
        return next_index

    if tuple(leader.pos) == route[index]:
        index = advance(index)
    # An unrelated friendly patrol may be travelling the opposite direction.
    # Skip its occupied waypoint so this leader can use the roadside shoulder
    # to pass it instead of waiting forever on a single-lane road.
    checked = set()
    while index not in checked and any(
        entity.team is leader.team
        and entity.squad is not squad
        and entity.pos == list(route[index])
        for entity in match_info.entities
    ):
        checked.add(index)
        index = advance(index)
    squad.patrolRouteIndex = index
    return route[index]


def _patrol_interrupted(squad):
    """Stop route-following as soon as the squad enters or detects combat."""
    if squad.inCombat:
        return True
    return any(
        mech.directlyVisibleEnemies or mech.trackedEnemies
        for mech in squad.mechList
    )


# ---------------------------------------------------------------------------
# First-pass AI combat
# ---------------------------------------------------------------------------

def _attack_ordered(squad):
    """Return whether the leader has issued a committed attack order."""
    goal_kind = getattr(squad.currentGoal, "kind", "")
    return squad.combatPosture == "attack" or goal_kind in {
        "attack", "attack_military_base", "eliminate_enemies",
    }


def _fire_suppressed(squad):
    """Return whether this squad's movement or posture forbids firing."""
    return squad.movementMode == "double_time" or squad.combatPosture in {
        "hold_fire", "stealth", "retreat",
    }


def _direct_ammo_ratio(mech):
    """Measure reusable direct-fire reserves without charging artillery ammo."""
    reserves = []
    for weapon in mech.mechClass.gunList:
        # Melee remains usable without ammunition, but it must not make a
        # nearly empty rifle loadout look well supplied at ranged contact.
        if weapon.isLauncher or weapon.isMelee:
            continue
        if weapon.charges is None:
            reserves.append(1)
        elif weapon.maxCharges:
            reserves.append(weapon.charges / weapon.maxCharges)
    return sum(reserves) / len(reserves) if reserves else 0


def _known_targets(mech):
    """Return only contacts the mech has received through normal sensing."""
    return [
        target
        for target in dict.fromkeys([*mech.directlyVisibleEnemies, *mech.trackedEnemies])
        if not target.destroyed and target.team is not mech.team
    ]


def _weapon_can_fire(mech, weapon, target):
    """Check shared resource and reach limits before considering a direct shot."""
    if weapon.isLauncher or weapon.hp <= 0:
        return False
    if weapon.charges is not None and weapon.charges <= 0:
        return False
    if weapon.apCost > mech.ap or weapon.energyCost > mech.energy:
        return False
    return weapon.maxRange is None or math.dist(mech.pos, target.pos) <= weapon.maxRange


def _best_direct_shot(match_info, mech, target):
    """Return a direct weapon, chance, and expected-damage score for target."""
    choices = []
    for weapon in mech.mechClass.gunList:
        if not _weapon_can_fire(mech, weapon, target):
            continue
        chance, _ = weapon.hit_chance_range(match_info, mech, target, target.pos)
        expected_damage = chance * weapon.dmg * weapon.projectileCount
        choices.append((expected_damage, chance, weapon))
    if not choices:
        return None, 0, 0
    expected_damage, chance, weapon = max(
        choices, key=lambda choice: (choice[0], choice[1], choice[2].name),
    )
    return weapon, chance, expected_damage


def _choose_target(match_info, squad, mech):
    """Choose the best sensed target allowed by this mech's firing doctrine."""
    visible = set(mech.directlyVisibleEnemies)
    aggressive_fire = _attack_ordered(squad) or _direct_ammo_ratio(mech) >= AI_GOOD_AMMO_THRESHOLD
    choices = []
    for target in _known_targets(mech):
        weapon, chance, expected_damage = _best_direct_shot(match_info, mech, target)
        if weapon is None:
            continue
        # A visually observed threat always merits a shot if one is possible.
        # Broader target engagement spends reserves only at a credible chance.
        if target not in visible and (not aggressive_fire or chance < AI_FIRE_ACCURACY_THRESHOLD):
            continue
        if target in visible and chance <= 0:
            continue
        choices.append((target in visible, expected_damage, chance, target, weapon))
    if not choices:
        return None, None, 0
    _, _, chance, target, weapon = max(
        choices,
        key=lambda choice: (
            choice[0], choice[1], choice[2], -math.dist(mech.pos, choice[3].pos), choice[3].name,
        ),
    )
    return target, weapon, chance


def _select_primary_target(squad):
    """Give the formation one known target to approach when it is attacking."""
    leader = squad.squadLead
    contacts = [target for mech in squad.mechList for target in _known_targets(mech)]
    contacts = list(dict.fromkeys(contacts))
    if not contacts:
        squad.primaryTarget = None
        return None
    squad.primaryTarget = min(
        contacts,
        key=lambda target: (math.dist(leader.pos, target.pos), target.mechClass.condition, target.name),
    )
    return squad.primaryTarget


def _fire_artillery_if_ordered(match_info, squad, mech, target):
    """Launch one round only under a committed attack command."""
    if not _attack_ordered(squad) or target is None or target.destroyed:
        return False
    for weapon in mech.mechClass.gunList:
        if not weapon.isLauncher:
            continue
        if weapon.apCost > mech.ap or weapon.energyCost > mech.energy:
            continue
        if weapon.launchAt(match_info, target.pos, shooter=mech):
            return True
    return False


def execute_squad_combat(match_info, squad=None):
    """Run one bounded, visibility-limited combat pass for a non-player squad.

    Direct weapons fire at visual threats whenever a shot can land. Mechs with
    healthy direct-ammo reserves, or an explicit attack order, may also engage
    sensed contacts at 65% or better. Attack orders retain a primary target so
    movement can close toward an 80% chance; artillery remains command-only.
    """
    squad = squad or match_info.pov.squad
    if squad.playerControlled or not squad.mechList or _fire_suppressed(squad):
        return []

    primary_target = _select_primary_target(squad)
    approach_targets = []
    fired = []
    squad.assignedTargets = {}
    for mech in list(squad.mechList):
        target, weapon, _ = _choose_target(match_info, squad, mech)
        if _attack_ordered(squad):
            for contact in _known_targets(mech):
                _, contact_chance, _ = _best_direct_shot(match_info, mech, contact)
                if contact_chance < AI_APPROACH_ACCURACY_THRESHOLD:
                    approach_targets.append(contact)
        if target is not None:
            squad.assignedTargets[mech] = target
            if weapon.shootAt(match_info, target.pos, shooter=mech):
                fired.append(mech)
        _fire_artillery_if_ordered(match_info, squad, mech, target or primary_target)
    if _attack_ordered(squad):
        squad.primaryTarget = min(
            dict.fromkeys(approach_targets),
            key=lambda target: (
                math.dist(squad.squadLead.pos, target.pos),
                target.mechClass.condition, target.name,
            ),
            default=None,
        )
    else:
        squad.primaryTarget = None
    return fired


def _energy_floor(mech, movement_mode):
    """Return the reserve a movement mode must leave after every step."""
    floor, _ = ENERGY_RESERVE_BANDS[movement_mode]
    return math.ceil(mech.mechClass.energyMax * floor)


def _energy_ceiling(mech, movement_mode):
    """Return the charge required to begin a new movement burst."""
    _, ceiling = ENERGY_RESERVE_BANDS[movement_mode]
    return math.ceil(mech.mechClass.energyMax * ceiling)


def _can_begin_movement(mech, movement_mode):
    """Require recharge to the policy ceiling before a new burst starts."""
    return mech.energy >= _energy_ceiling(mech, movement_mode)


def _in_patrol_corridor(position, patrol_route):
    """Return whether a cell is on or one tile beside the selected route."""
    return any(
        max(abs(position[0] - route_tile[0]), abs(position[1] - route_tile[1]))
        <= ROAD_PATROL_WIGGLE_RADIUS
        for route_tile in patrol_route
    )


def _legal_steps(match_info, mech, movement_mode, roadway_only=False, patrol_route=()):
    """Yield shared-rules steps that obey a squad's energy reserve policy."""
    restrict_to_corridor = (
        roadway_only
        and patrol_route
        and _in_patrol_corridor(mech.pos, patrol_route)
    )
    for offset_x, offset_y in _ADJACENT_OFFSETS:
        position = [mech.pos[0] + offset_x, mech.pos[1] + offset_y]
        energy_cost, reason = mech.moveCostTo(match_info, position)
        if reason is None and mech.energy - energy_cost >= _energy_floor(mech, movement_mode):
            if restrict_to_corridor and not _in_patrol_corridor(position, patrol_route):
                continue
            yield position, energy_cost


def _nearest_roadway(match_info, position):
    """Return the nearest road/tunnel tile so an off-road patrol can join it."""
    roads = [
        cell.pos
        for row in match_info.map
        for cell in row
        if _is_roadway(match_info, cell.pos)
    ]
    return _nearest_location(position, roads) if roads else None


def _formation_status(position, leader_position, teammate_positions, leader_range):
    """Return leader-tether and teammate-spacing results for one position."""
    leader_distance = math.dist(position, leader_position)
    nearest_teammate = min(
        (math.dist(position, teammate_position) for teammate_position in teammate_positions),
        default=float("inf"),
    )
    return (
        leader_distance <= leader_range,
        nearest_teammate >= FORMATION_SPACING,
        leader_distance,
        nearest_teammate,
    )


def _leader_needs_regroup(squad, leader_range):
    """Return whether any follower needs range or spacing correction."""
    leader = squad.squadLead
    for mech in squad.mechList:
        if mech is leader:
            continue
        teammates = [other.pos for other in squad.mechList if other is not mech]
        within_range, spaced, _, _ = _formation_status(
            mech.pos, leader.pos, teammates, leader_range,
        )
        if not within_range or not spaced:
            return True
    return False


def _squad_ready_to_advance(squad):
    """Return whether every squad member has recharged for its next movement burst.

    Once the squad is both regrouped and spaced, the leader holds until every
    member has recovered to the selected movement mode's ceiling.  This lets
    catch-up movement use costly terrain without splitting the formation.
    """
    return all(
        _can_begin_movement(mech, squad.movementMode)
        for mech in squad.mechList
    )


def _move_leader(match_info, squad, leader_range, roadway_only):
    """Advance the leader until it reaches its reserve, goal, or regroup hold."""
    leader = squad.squadLead
    if not _squad_ready_to_advance(squad):
        return []
    moved = []
    while not _leader_needs_regroup(squad, leader_range):
        destination = _leader_destination(match_info, squad)
        if roadway_only and not _is_roadway(match_info, leader.pos):
            destination = _nearest_roadway(match_info, leader.pos)
        if destination is None:
            break
        current_distance = math.dist(leader.pos, destination)
        steps = [
            (math.dist(position, destination), energy_cost, position)
            for position, energy_cost in _legal_steps(
                match_info, leader, squad.movementMode, roadway_only, squad.patrolRoute,
            )
        ]
        if not steps:
            break
        progressing_steps = [step for step in steps if step[0] < current_distance]
        if progressing_steps:
            _, _, position = min(
                progressing_steps,
                key=lambda option: (option[1], option[0], option[2]),
            )
        else:
            # A roadside shoulder can be temporarily less direct than the
            # destination. Allow one such step so allied patrols do not lock
            # each other in place on a one-tile road.
            wiggle_steps = [
                step for step in steps
                if step[0] <= current_distance + ROAD_PATROL_WIGGLE_RADIUS
            ]
            if not roadway_only or not wiggle_steps:
                break
            _, _, position = min(wiggle_steps, key=lambda option: (option[0], option[1], option[2]))
        if not leader.moveTo(match_info, position, announce=False):
            break
        moved.append(leader)
    return moved


def _move_follower(match_info, squad, mech, leader_range, roadway_only):
    """Correct a follower's leader tether and spacing during any regroup."""
    leader = squad.squadLead
    moved = []
    # This includes close-together units: spacing is kept even while another
    # follower is catching up, so the formation does not pile up at the lead.
    if not _can_begin_movement(mech, squad.movementMode):
        return moved
    while True:
        teammate_positions = [
            teammate.pos for teammate in squad.mechList if teammate is not mech
        ]
        current = _formation_status(mech.pos, leader.pos, teammate_positions, leader_range)
        if current[0] and current[1]:
            break

        candidates = []
        for position, energy_cost in _legal_steps(
            match_info, mech, squad.movementMode, roadway_only, squad.patrolRoute,
        ):
            status = _formation_status(position, leader.pos, teammate_positions, leader_range)
            candidates.append((status, energy_cost, position))
        if not candidates:
            break

        valid = [candidate for candidate in candidates if candidate[0][0] and candidate[0][1]]
        if valid:
            _, _, position = min(
                valid,
                key=lambda candidate: (
                    candidate[1], -candidate[0][3], candidate[0][2], candidate[2],
                ),
            )
        else:
            # Constrained ground may make perfect spacing impossible. Favor a
            # position inside leader range, then the best available separation.
            _, _, position = max(
                candidates,
                key=lambda candidate: (
                    candidate[0][0], candidate[0][3], -candidate[1], -candidate[0][2],
                ),
            )
        if not mech.moveTo(match_info, position, announce=False):
            break
        moved.append(mech)
    return moved


def execute_squad_movement(match_info, squad=None):
    """Perform visibility-limited AI movement under squad reserve policies.

    Leaders hold to correct both the visual tether (at least 10 tiles) and
    three-tile unit spacing. Followers keep spacing even while another unit
    is regrouping. After regrouping, the leader waits for every member to
    reach the mode's burst ceiling before advancing. Patrol/defense squads
    follow a recorded road route, reversing at its endpoint, until combat or
    a contact interrupts them. Patrol bursts run from 95 to 85 percent energy,
    normal movement from 90 to 70, and double time from 50 to 20.
    """
    squad = squad or match_info.pov.squad
    if squad.playerControlled or not squad.mechList or squad.squadLead is None:
        return []

    leader_range = max(MIN_LEADER_VISUAL_RANGE, squad.squadLead.visPower)
    roadway_only = _road_patrol_active(squad)
    if roadway_only:
        _ensure_road_patrol(match_info, squad)
        if _patrol_interrupted(squad):
            return []
        roadway_only = bool(squad.patrolRoute)
    moved = _move_leader(match_info, squad, leader_range, roadway_only)
    for mech in list(squad.mechList):
        if mech is squad.squadLead:
            continue
        moved.extend(_move_follower(match_info, squad, mech, leader_range, roadway_only))
    return moved


# TODO(ai-execution): extend this bounded movement pass into a planner that
# consumes only team-shared vision, radar contacts, squad readiness, and
# current goals. It should emit typed orders (advance, hold, scout, engage,
# support, withdraw) that a separate action executor can validate through the
# normal movement/combat rules. Do not call player command menus or inspect
# enemy-only state here.
