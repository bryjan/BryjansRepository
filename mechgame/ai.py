"""Data-only strategic AI planning shared by matches, teams, and squads.

This module deliberately assigns intent without issuing movement or combat
commands. The later team, squad-leader, faction, and pilot layers build on the
same goal objects rather than inventing their own incompatible state.
"""

from dataclasses import dataclass

__all__ = ["TeamGoal", "assign_team_goals"]


@dataclass(frozen=True)
class TeamGoal:
    """One match-issued strategic order for a team.

    ``target_tiles`` holds immutable coordinates so goals can refer to map
    features without retaining mutable Cell objects. ``objective_id`` remains
    empty for non-objective goals such as eliminating the opposing force.
    """

    kind: str
    priority: int
    target_tiles: tuple[tuple[int, int], ...] = ()
    objective_id: str | None = None
    description: str = ""


def _goal_for_objective(objective):
    """Translate one scenario objective into the neutral default team order."""
    return TeamGoal(
        kind="secure_objective",
        priority=100,
        target_tiles=objective.tiles,
        objective_id=objective.objective_id,
        description=f"Secure {objective.name}.",
    )


def assign_team_goals(match_info):
    """Give every team a stable starting goal after scenario setup is complete.

    Scenario objectives take precedence. Until scenarios define ownership or
    asymmetric objective rules, every team receives the same neutral order to
    secure the first declared objective. Objective-free skirmishes retain the
    familiar elimination win condition.
    """
    objective = next(iter(match_info.mapFeatures.objectives), None)
    for team in match_info.teamList:
        goal = _goal_for_objective(objective) if objective else TeamGoal(
            kind="eliminate_enemies",
            priority=100,
            description="Eliminate all opposing operational mechs.",
        )
        team.currentGoal = goal
        team.goalHistory.append(goal)
