"""Strategic objective assignment and visibility-limited squad movement.

This module validates and distributes objectives, then executes a bounded
first movement pass. It never reads hidden enemy or map information, leaving
combat choices for the future squad-leader action planner.
"""

from dataclasses import dataclass
import math

from . import artillery

__all__ = [
    "SquadGoal", "TeamGoal", "assign_team_goals", "assign_team_goals_to_squads",
    "execute_squad_combat", "execute_squad_movement", "issue_team_goal",
    "request_reinforcement", "start_road_patrol",
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
ANTI_HEAVY_FORCE_TOLERANCE = .35
NEARBY_SQUAD_SUPPORT_RANGE = 20
ARTILLERY_MIN_FORCE_RATIO = .80
ARTILLERY_MAX_FORCE_RATIO = 1.50
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
    if squad.avoidContact and squad.avoidanceTarget is not None:
        return squad.avoidanceTarget
    patrol_destination = (
        _patrol_destination(match_info, squad, leader)
        if _road_patrol_active(squad) else None
    )
    if patrol_destination is not None:
        return patrol_destination
    target = squad.primaryTarget
    if (
        (_attack_ordered(squad) or squad.engagementAssessment == "favorable")
        and target in match_info.entities and not target.destroyed
    ):
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

def _entity_combat_force(entity):
    """Estimate one observed mech's force without reading its hidden damage."""
    return (3 ** (entity.size - 2)) * entity.mechClass.combatForceMultiplier


def _nearby_friendly_squads(squad):
    """Return friendly squads close enough to count as immediate support."""
    if not getattr(squad, "team", None) or squad.squadLead is None:
        return []
    return [
        other for other in squad.team.squadsList
        if other.mechList and other.squadLead is not None
        and math.dist(squad.squadLead.pos, other.squadLead.pos) <= NEARBY_SQUAD_SUPPORT_RANGE
    ]


def _combat_target(entity):
    """Return whether an observed mech is a combat target, not pure support."""
    combat_roles = {
        "front_line", "anchor", "assault", "combat", "skirmisher",
        "anti_heavy", "anti_swarm",
    }
    return bool(combat_roles & set(entity.mechClass.roles))


def _avoidance_destination(match_info, squad, threat):
    """Choose an in-bounds point directly away from an overwhelming contact."""
    leader = squad.squadLead
    delta_x = leader.pos[0] - threat.pos[0]
    delta_y = leader.pos[1] - threat.pos[1]
    distance = max(1, math.hypot(delta_x, delta_y))
    retreat_distance = max(MIN_LEADER_VISUAL_RANGE, leader.visPower)
    target_x = round(leader.pos[0] + (delta_x / distance) * retreat_distance)
    target_y = round(leader.pos[1] + (delta_y / distance) * retreat_distance)
    return (
        min(max(1, target_x), match_info.mapWidth - 2),
        min(max(1, target_y), match_info.mapHeight - 2),
    )


def _assess_enemy_force(match_info, squad, contacts):
    """Store observed force balance; damage review decides commitment later."""
    nearby_squads = _nearby_friendly_squads(squad)
    squad.nearbyFriendlyForce = round(sum(other.combatForce for other in nearby_squads), 2)
    squad.observedEnemyForce = round(sum(_entity_combat_force(contact) for contact in contacts), 2)
    friendly_force = squad.nearbyFriendlyForce
    if not contacts or friendly_force <= 0:
        squad.avoidContact = False
        squad.avoidanceTarget = None
        return

    force_ratio = squad.observedEnemyForce / friendly_force
    highest_threat = max(
        contacts,
        key=lambda contact: (_entity_combat_force(contact), -math.dist(squad.squadLead.pos, contact.pos)),
    )
    # Force alone is recorded immediately, but the leader waits for two
    # combat turns of confirmed damage before committing or disengaging.
    squad.forceRatio = force_ratio
    squad.strongestObservedThreat = highest_threat


def _squad_resources_high(squad):
    """Return whether the squad can safely continue an unclear exchange."""
    if not squad.mechList:
        return False
    average_integrity = sum(mech.mechClass.condition for mech in squad.mechList) / len(squad.mechList)
    average_ammo = sum(mech.readinessMetrics.get("ammo", 100) for mech in squad.mechList) / len(squad.mechList)
    return average_integrity >= 60 and average_ammo >= 50


def _squad_has_artillery_reserves(squad):
    """Return whether an artillery squad has at least half its shell pool."""
    reserves = [
        ammo.charges / ammo.maxCharges
        for mech in squad.mechList
        for weapon in mech.mechClass.gunList if weapon.isLauncher
        for ammo in weapon.ammoTypes
        if ammo.charges is not None and ammo.maxCharges
    ]
    return bool(reserves) and sum(reserves) / len(reserves) >= .50


def _review_engagement(match_info, squad, contacts):
    """Review two turns of damage with intentional leader uncertainty."""
    if not contacts or not squad.inCombat:
        squad.combatTurns = 0
        squad.damageGiven = 0
        squad.damageReceived = 0
        squad.engagementAssessment = "unassessed"
        return
    squad.combatTurns += 1
    if squad.combatTurns < 2:
        squad.engagementAssessment = "unassessed"
        return

    error = max(0, getattr(squad.squadLead, "combatAssessmentError", .25))
    squad.estimatedDamageGiven = round(squad.damageGiven * match_info.rng.uniform(1 - error, 1 + error), 1)
    squad.estimatedDamageReceived = round(squad.damageReceived * match_info.rng.uniform(1 - error, 1 + error), 1)
    given = squad.estimatedDamageGiven
    received = squad.estimatedDamageReceived
    if given > received * 1.20:
        squad.engagementAssessment = "favorable"
    elif received > given * 1.20 or getattr(squad, "forceRatio", 0) > ARTILLERY_MAX_FORCE_RATIO:
        squad.engagementAssessment = "unfavorable"
    else:
        squad.engagementAssessment = "unclear"

    squad.avoidContact = squad.engagementAssessment == "unfavorable"
    threat = getattr(squad, "strongestObservedThreat", None)
    squad.avoidanceTarget = (
        _avoidance_destination(match_info, squad, threat)
        if squad.avoidContact and threat is not None else None
    )


def _notify_player_support_request(match_info, recipient, message):
    """Surface a support request as a critical report for player control."""
    if recipient.playerControlled and recipient.squadLead is not None:
        recipient.squadLead.report(match_info, message, critical=True)


def request_reinforcement(match_info, requesting_squad, recipient_squad):
    """Record a future reinforcement request and notify a player recipient.

    Reinforcement movement is intentionally a later planner feature; the
    request record and player-facing critical report are ready for it now.
    """
    recipient_squad.reinforcementRequest = requesting_squad
    _notify_player_support_request(
        match_info, recipient_squad,
        f"Reinforcement request from {requesting_squad.name} squad.",
    )


def _issue_artillery_call(match_info, squad):
    """Call high-reserve artillery only during an unclear engagement."""
    squad.artilleryCallTarget = None
    squad.artilleryCallTurns = 0
    if squad.engagementAssessment != "unclear":
        return
    target = getattr(squad, "strongestObservedThreat", None)
    if target is None:
        return
    nearby = _nearby_friendly_squads(squad)
    eligible = [candidate for candidate in nearby if _squad_has_artillery_reserves(candidate)]
    if not eligible:
        return
    for artillery_squad in eligible:
        artillery_squad.artilleryCallTarget = target
        artillery_squad.artilleryCallTurns = 1
        _notify_player_support_request(
            match_info, artillery_squad,
            f"Artillery request from {squad.name} squad: engage {target.name}.",
        )


def _can_smoke_position(match_info, mech, weapon, position):
    """Return whether one launcher has a loaded smoke shell that can reach."""
    for index, ammo in enumerate(weapon.ammoTypes):
        if ammo.payload != "smoke" or ammo.charges == 0:
            continue
        distance = math.dist(mech.pos, position)
        if weapon.launcher_profile(distance, match_info, mech) is not None:
            return index
    return None


def _issue_retreat_smoke_call(match_info, squad):
    """Ask any in-range friendly artillery to screen a retreating squad."""
    if not squad.inCombat or squad.squadLead is None:
        return
    position = tuple(squad.squadLead.pos)
    for artillery_squad in squad.team.squadsList:
        # A retreating formation has its own fire suppressed, so it cannot
        # provide the screening fire it is requesting.
        if artillery_squad is squad or _fire_suppressed(artillery_squad):
            continue
        for mech in artillery_squad.mechList:
            for weapon in mech.mechClass.gunList:
                if not weapon.isLauncher or _can_smoke_position(match_info, mech, weapon, position) is None:
                    continue
                artillery_squad.smokeCallPosition = position
                artillery_squad.smokeCallTurns = 1
                _notify_player_support_request(
                    match_info, artillery_squad,
                    f"Smoke request from {squad.name} squad at {list(position)}.",
                )
                # One screen is enough; preserve the rest of the team's
                # scarce smoke rounds for later withdrawals.
                return
            else:
                continue


def _assign_anti_heavy_focus(squad, contacts):
    """Concentrate a near-matching anti-heavy group on one combat mech."""
    anti_heavies = [
        mech for mech in squad.mechList
        if "anti_heavy" in mech.mechClass.roles and mech.combatReady
    ]
    combat_targets = [target for target in contacts if _combat_target(target)]
    if not anti_heavies or not combat_targets:
        return

    combined_force = sum(_entity_combat_force(mech) for mech in anti_heavies)
    candidates = []
    for target in combat_targets:
        target_force = _entity_combat_force(target)
        difference = abs(combined_force - target_force) / max(combined_force, target_force)
        if difference <= ANTI_HEAVY_FORCE_TOLERANCE:
            candidates.append((difference, -target_force, target))
    if not candidates:
        return
    _, _, focus_target = min(candidates, key=lambda candidate: (candidate[0], candidate[1], candidate[2].name))
    for mech in anti_heavies:
        if focus_target in _known_targets(mech):
            squad.assignedTargets[mech] = focus_target

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
    assigned_target = squad.assignedTargets.get(mech)
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
    if assigned_target is not None:
        assigned_choice = next(
            (choice for choice in choices if choice[3] is assigned_target), None,
        )
        if assigned_choice is not None:
            _, _, chance, target, weapon = assigned_choice
            return target, weapon, chance
    if "anti_swarm" in mech.mechClass.roles:
        # Anti-swarm fire remains opportunistic. It does not consume a leader
        # assignment: damaged, close threats are preferable targets.
        _, _, chance, target, weapon = max(
            choices,
            key=lambda choice: (
                choice[0], -choice[3].mechClass.condition,
                -math.dist(mech.pos, choice[3].pos), choice[1], choice[2], choice[3].name,
            ),
        )
    else:
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


def _artillery_position_is_safe(match_info, shooter, weapon, position):
    """Reject an explosive impact whose scatter-and-blast area reaches allies."""
    ammo = weapon.selected_ammo
    if ammo.payload not in {"explosive", "incendiary"}:
        return True
    profile = weapon.launcher_profile(math.dist(shooter.pos, position), match_info, shooter)
    if profile is None:
        return False
    danger_radius = ammo.blastRadius + profile["inaccuracy"]
    return not any(
        entity is not shooter
        and entity.team is shooter.team
        and math.dist(entity.pos, position) <= danger_radius
        for entity in match_info.entities
    )


def _artillery_target_position(match_info, shooter, weapon, target):
    """Prefer a safe lead, then the target cell; hold fire if both are unsafe."""
    lead = artillery.predict_launcher_lead(match_info, weapon, target, shooter)
    if lead is not None and _artillery_position_is_safe(match_info, shooter, weapon, lead):
        return lead
    target_position = list(target.pos)
    if _artillery_position_is_safe(match_info, shooter, weapon, target_position):
        return target_position
    return None


def _fire_artillery_if_ordered(match_info, squad, mech):
    """Launch one requested smoke shell or a safe offensive artillery round."""
    smoke_position = (
        squad.smokeCallPosition if squad.smokeCallTurns > 0 else None
    )
    for weapon in mech.mechClass.gunList:
        if not weapon.isLauncher:
            continue
        if weapon.apCost > mech.ap or weapon.energyCost > mech.energy:
            continue

        # Smoke has priority: the requesting squad is actively withdrawing,
        # whereas an offensive call can wait for the next artillery pass.
        if smoke_position is not None:
            smoke_index = _can_smoke_position(
                match_info, mech, weapon, smoke_position,
            )
            if smoke_index is not None:
                weapon.select_ammo(smoke_index)
                if weapon.launchAt(match_info, smoke_position, shooter=mech):
                    return True

        target = squad.artilleryCallTarget
        if target is None or target.destroyed:
            continue
        position = _artillery_target_position(match_info, mech, weapon, target)
        if position is not None and weapon.launchAt(match_info, position, shooter=mech):
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
    if not squad.mechList:
        return []
    if squad.combatPosture == "retreat" and squad.inCombat:
        _issue_retreat_smoke_call(match_info, squad)
    if squad.playerControlled or _fire_suppressed(squad):
        return []

    contacts = list(dict.fromkeys(
        target for mech in squad.mechList for target in _known_targets(mech)
    ))
    incoming_artillery_call = (
        squad.artilleryCallTarget if squad.artilleryCallTurns > 0 else None
    )
    squad.assignedTargets = {}
    _assess_enemy_force(match_info, squad, contacts)
    _review_engagement(match_info, squad, contacts)
    if squad.avoidContact:
        squad.primaryTarget = None
        return []

    if incoming_artillery_call is not None:
        squad.artilleryCallTarget = incoming_artillery_call
        squad.artilleryCallTurns = 1
    else:
        _issue_artillery_call(match_info, squad)

    _assign_anti_heavy_focus(squad, contacts)
    primary_target = _select_primary_target(squad)
    approach_targets = []
    fired = []
    for mech in list(squad.mechList):
        target, weapon, _ = _choose_target(match_info, squad, mech)
        if _attack_ordered(squad):
            for contact in _known_targets(mech):
                _, contact_chance, _ = _best_direct_shot(match_info, mech, contact)
                if contact_chance < AI_APPROACH_ACCURACY_THRESHOLD:
                    approach_targets.append(contact)
        if target is not None:
            squad.assignedTargets.setdefault(mech, target)
            if weapon.shootAt(match_info, target.pos, shooter=mech):
                fired.append(mech)
        _fire_artillery_if_ordered(match_info, squad, mech)
    if squad.engagementAssessment == "favorable":
        squad.primaryTarget = getattr(squad, "strongestObservedThreat", None)
    elif _attack_ordered(squad):
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
    if squad.artilleryCallTurns:
        squad.artilleryCallTurns -= 1
        if squad.artilleryCallTurns == 0:
            squad.artilleryCallTarget = None
    if squad.smokeCallTurns:
        squad.smokeCallTurns -= 1
        if squad.smokeCallTurns == 0:
            squad.smokeCallPosition = None
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
            # An overwhelmed patrol abandons the route and follows the
            # leader's avoidance destination instead of freezing in place.
            if squad.avoidContact:
                roadway_only = False
            else:
                return []
        else:
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
