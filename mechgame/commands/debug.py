"""Explicit, read-only inspection of enemy orders and decision/report logs."""

import textwrap

from ..ui import tactical as pv


def enemy_orders(match):
    lines = ["DEBUG: hidden enemy information"]
    for team in match.teamList:
        if team is match.pov.team:
            continue
        lines.append(f"TEAM: {team.name}")
        lines.extend(f"Team objective: {goal.kind} | priority {goal.priority} | {goal.message}"
                     for goal in team.currentGoals)
        for squad in team.squadsList:
            lines.extend(["", f"SQUAD: {squad.name} ({len(squad.mechList)} mechs)"])
            if not squad.mechList:
                lines.append("No operational units.")
                continue
            lines.append(f"SL: {squad.squadLead.pilot.display_name} at {squad.squadLead.pos}")
            goal = squad.currentGoal
            lines.append(f"Order: {goal.kind if goal else 'None'} | priority {goal.priority if goal else 0}")
            if goal:
                lines.extend([goal.message, f"Locations: {list(goal.locations[:4])}"])
            lines.extend([
                f"Posture: {squad.combatPosture} | Movement: {squad.movementMode}/{squad.movementBehavior}",
                f"Force: {squad.combatForce} | Effective: {squad.combatEffective} | Flee: {squad.fleeOrdered}",
                f"Combat assessment: {squad.engagementAssessment} | Avoid: {squad.avoidContact}",
            ])
            if squad.patrolRoute:
                lines.append(f"Patrol: {squad.patrolRouteId}, waypoint {squad.patrolRouteIndex}, direction {squad.patrolRouteDirection}")
            if squad.ambushLocation is not None:
                lines.append(f"Ambush: {squad.ambushLocation}, triggered={squad.ambushTriggered}, linked squads={len(squad.ambushGroup)}")
            if squad.combinedAttack is not None:
                order = squad.combinedAttack
                lines.append(f"Combined order: {order.kind}/{order.state}; plotted targets {list(order.target_positions.values())}")
            if squad.investigationPosition is not None:
                lines.append(f"Investigating: {squad.investigationPosition}")
            lines.append("Units: " + "; ".join(
                f"{mech.pilot.display_name} {mech.pos} AP {mech.ap} MP {mech.mp} EN {mech.energy}/{mech.mechClass.energyMax}"
                for mech in squad.mechList))
    return lines


def enemy_logs(match):
    lines = ["DEBUG: enemy decision logs and reports"]
    for team in match.teamList:
        if team is match.pov.team:
            continue
        lines.append(f"TEAM: {team.name}")
        lines.extend(report[0] for report in team.reportLog)
        for squad in team.squadsList:
            lines.extend(["", f"SQUAD: {squad.name}", "AI decisions (newest first):"])
            lines.extend(f"Round {turn}: {message}" for turn, message in reversed(squad.aiLog))
            if not squad.aiLog:
                lines.append("No AI decisions recorded yet.")
            lines.append("Order history (newest first):")
            lines.extend(f"{goal.kind} | priority {goal.priority} | {list(goal.locations[:4])} | {goal.message}"
                         for goal in reversed(squad.goalHistory[-20:]))
            lines.append("Squad reports (newest first):")
            lines.extend(report[0] for report in squad.reportLog)
            if not squad.reportLog:
                lines.append("No reports.")
    return lines


def inspect_enemy(match, logs=False):
    """Inspect snapshots without revealing terrain or altering report read flags."""
    content = enemy_logs(match) if logs else enemy_orders(match)
    rows = [line for entry in content for line in (textwrap.wrap(entry, pv.SIDE_PANEL_WIDTH) or [""])]
    count = max(1, match.windowHeight - 3)
    pages = max(1, (len(rows) + count - 1) // count)
    page = 0
    while True:
        pv.print_overview(match,
                          command_text="AI debug: 'n' next | 'p' previous | 'x' back",
                          right_panel=(f"ENEMY {'LOGS' if logs else 'ORDERS'} {page + 1}/{pages}", rows[page * count:(page + 1) * count]))
        choice = input("AI debug: ").strip().lower()
        if choice in {"", "x"}:
            return
        if choice == "n":
            page = min(pages - 1, page + 1)
        elif choice == "p":
            page = max(0, page - 1)
