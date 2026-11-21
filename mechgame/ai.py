"""Data-only strategic AI planning shared by matches, teams, and squads.

This module assigns intent without issuing movement or combat commands. The
later team, squad-leader, faction, and pilot layers all use these same ordered
objective records rather than inventing incompatible state.
"""

from dataclasses import dataclass

__all__ = ["TeamGoal", "assign_team_goals", "issue_team_goal"]


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


def _coordinates(locations):
    """Normalize Cells and coordinate pairs into immutable locations."""
    return tuple(
        tuple(location.pos) if hasattr(location, "pos") else tuple(location)
        for location in locations
    )


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
