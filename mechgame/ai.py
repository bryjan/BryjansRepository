"""Strategic objective assignment shared by matches, teams, and squads.

This module intentionally stops at *intent*: it validates and distributes
objectives, but it never reads hidden map information or issues a move/fire
action. Keeping that boundary explicit lets the future squad-leader planner
turn visible state into orders without coupling AI decisions to terminal UI.
"""

from dataclasses import dataclass

__all__ = [
    "SquadGoal", "TeamGoal", "assign_team_goals", "assign_team_goals_to_squads",
    "issue_team_goal",
]


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


# TODO(ai-execution): add a planner that consumes only team-shared vision,
# radar contacts, squad readiness, and current goals. It should emit typed
# squad orders (advance, hold, scout, engage, support, withdraw) that a
# separate action executor can validate through the normal movement/combat
# rules. Do not call player command menus or inspect enemy-only state here.
