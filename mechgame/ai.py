"""Strategic objective assignment shared by matches, teams, and squads.

This module intentionally stops at *intent*: it validates and distributes
objectives, but it never reads hidden map information or issues a move/fire
action. Keeping that boundary explicit lets the future squad-leader planner
turn visible state into orders without coupling AI decisions to terminal UI.
"""

from dataclasses import dataclass
import math

__all__ = [
    "SquadGoal", "TeamGoal", "assign_team_goals", "assign_team_goals_to_squads",
    "execute_squad_movement", "issue_team_goal",
]


FORMATION_SPACING = 3
MIN_LEADER_VISUAL_RANGE = 10
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
    if squad.currentGoal and squad.currentGoal.locations:
        return _nearest_location(leader.pos, squad.currentGoal.locations)
    # Direct sight and radar tracking are both already filtered by the normal
    # sensing system. Do not inspect arbitrary enemies in the match here.
    contacts = [*leader.directlyVisibleEnemies, *leader.trackedEnemies]
    if contacts:
        return _nearest_location(leader.pos, [contact.pos for contact in contacts])
    if squad.currentGoal and squad.currentGoal.kind == "eliminate_enemies":
        # This neutral search point is map knowledge, not hidden enemy data.
        # TODO(ai-search): replace it with leader-selected patrol routes and
        # unexplored-frontier scouting once the planner owns search behavior.
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
        "patrol", "patrol_map", "patrol_location",
    }


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


def _legal_steps(match_info, mech, movement_mode, roadway_only=False):
    """Yield shared-rules steps that obey a squad's energy reserve policy."""
    restrict_to_roadway = roadway_only and _is_roadway(match_info, mech.pos)
    for offset_x, offset_y in _ADJACENT_OFFSETS:
        position = [mech.pos[0] + offset_x, mech.pos[1] + offset_y]
        energy_cost, reason = mech.moveCostTo(match_info, position)
        if reason is None and mech.energy - energy_cost >= _energy_floor(mech, movement_mode):
            if restrict_to_roadway and not _is_roadway(match_info, position):
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


def _leader_needs_regroup(squad, leader_range):
    """Return whether any follower has fallen outside the leader's sight range."""
    return any(
        math.dist(mech.pos, squad.squadLead.pos) > leader_range
        for mech in squad.mechList
        if mech is not squad.squadLead
    )


def _move_leader(match_info, squad, leader_range, roadway_only):
    """Advance the leader until it reaches its reserve, goal, or regroup hold."""
    leader = squad.squadLead
    destination = _leader_destination(match_info, squad)
    if roadway_only and not _is_roadway(match_info, leader.pos):
        destination = _nearest_roadway(match_info, leader.pos)
    if destination is None:
        return []
    if not _can_begin_movement(leader, squad.movementMode):
        return []
    moved = []
    while not _leader_needs_regroup(squad, leader_range):
        current_distance = math.dist(leader.pos, destination)
        steps = [
            (math.dist(position, destination), energy_cost, position)
            for position, energy_cost in _legal_steps(
                match_info, leader, squad.movementMode, roadway_only,
            )
        ]
        if not steps:
            break
        _, _, position = min(steps, key=lambda option: (option[1], option[0], option[2]))
        if math.dist(position, destination) >= current_distance:
            break
        if not leader.moveTo(match_info, position, announce=False):
            break
        moved.append(leader)
    return moved


def _formation_status(position, leader_position, teammate_positions, leader_range):
    """Return whether one position meets leader-range and spacing constraints."""
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


def _move_follower(match_info, squad, mech, leader_range, roadway_only):
    """Move a follower until it reaches a valid formation or reserve floor."""
    leader = squad.squadLead
    moved = []
    # A leader already holds while this mech is outside the visual tether.
    # Waiting here lets the follower recharge to its mode's ceiling before it
    # attempts an expensive catch-up route.
    if not _can_begin_movement(mech, squad.movementMode):
        return moved
    while True:
        teammate_positions = [
            teammate.pos for teammate in squad.mechList if teammate is not mech
        ]
        current = _formation_status(mech.pos, leader.pos, teammate_positions, leader_range)
        spacing_valid = roadway_only or current[1]
        if current[0] and spacing_valid:
            # Holding a valid position costs no energy and is therefore preferred.
            break

        candidates = []
        for position, energy_cost in _legal_steps(
            match_info, mech, squad.movementMode, roadway_only,
        ):
            status = _formation_status(position, leader.pos, teammate_positions, leader_range)
            candidates.append((status, energy_cost, position))
        if not candidates:
            break

        valid = [
            candidate for candidate in candidates
            if candidate[0][0] and (roadway_only or candidate[0][1])
        ]
        if valid:
            _, _, position = min(
                valid,
                key=lambda candidate: (
                    candidate[1], -candidate[0][3], candidate[0][2], candidate[2],
                ),
            )
        else:
            # Constrained terrain can make perfect spacing impossible. Favor a
            # tile inside leader range, then the greatest available separation.
            _, _, position = max(
                candidates,
                key=lambda candidate: (
                    candidate[0][0], roadway_only or candidate[0][1], candidate[0][3],
                    -candidate[1], -candidate[0][2],
                ),
            )
        if not mech.moveTo(match_info, position, announce=False):
            break
        moved.append(mech)
    return moved


def execute_squad_movement(match_info, squad=None):
    """Perform visibility-limited AI movement under squad reserve policies.

    Leaders hold to regroup any follower outside their plains visual range
    (at least 10 tiles). Otherwise they advance first. Formation followers
    seek three-tile spacing; road patrols stay on roads/tunnels and deliberately
    ignore that spacing so a column can travel together. Patrol bursts run from
    95 to 85 percent energy, normal movement from 90 to 70, and double time
    from 50 to 20. Out-of-range followers wait to reach their burst ceiling
    while the leader holds position for regrouping.
    """
    squad = squad or match_info.pov.squad
    if squad.playerControlled or not squad.mechList or squad.squadLead is None:
        return []

    leader_range = max(MIN_LEADER_VISUAL_RANGE, squad.squadLead.visPower)
    roadway_only = _road_patrol_active(squad)
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
