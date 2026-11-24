"""Persistent battle totals and player-facing after-action summaries."""

def summary(match):
    """Build results from all surviving and removed units, without AI estimates."""
    roster = list(dict.fromkeys([
        *match.entities, *match.destroyedMechs, *match.abandonedMechs, *match.fledMechs,
    ]))
    lines = ["AFTER ACTION", match.resultMessage, ""]
    for team in match.teamList:
        units = [mech for mech in roster if mech.team is team]
        destroyed = [mech for mech in units if mech in match.destroyedMechs]
        dead = [mech.pilot.display_name for mech in units if mech.pilot in match.killedPilots]
        missing = [mech.pilot.display_name for mech in units if mech.pilot.status in {"MIA", "Evading"}]
        lines.extend([
            team.name,
            f"Damage dealt: {match.damageDealt.get(team, 0):.0f} | Received: {match.damageReceived.get(team, 0):.0f}",
            f"Mechs destroyed: {len(destroyed)} | Extracted: {sum(mech in match.fledMechs for mech in units)}",
            "Destroyed: " + (", ".join(f"{mech.pilot.display_name} ({mech.mechClass.name})" for mech in destroyed) or "none"),
            f"Pilots lost: {len(dead) + len(missing)} | Killed: {', '.join(dead) or 'none'} | Missing/evading: {', '.join(missing) or 'none'}",
        ])
        if match.raidObjective is not None:
            raid = match.raidObjective
            if team is raid.player:
                lines.append(f"Raid Military Base: {'COMPLETED' if raid.raided else 'FAILED'}")
                lines.append("Extract force: " + ("COMPLETED" if not any(s.mechList for s in team.squadsList)
                             and any(mech in match.fledMechs for mech in units) else "NOT COMPLETED"))
                lines.append("Clear enemy field: " + ("COMPLETED" if not any(s.mechList for s in raid.defender.squadsList) else "NOT COMPLETED"))
            else:
                lines.append(f"Prevent base raid: {'FAILED' if raid.raided else 'COMPLETED'}")
        elif not match.missions:
            lines.append(f"Defeat opposing forces: {'COMPLETED' if match.winner is team else 'FAILED'}")
        else:
            lines.append("Other objectives: no completion evaluator recorded.")
        lines.append("")
    return lines


def show(match):
    """Page results within the configured display before returning to the menu."""
    from types import SimpleNamespace
    from .ui.menu import _frame
    import textwrap
    settings = SimpleNamespace(display_width=match.displayWidth, display_height=match.displayHeight)
    width = max(40, settings.display_width - 4)
    lines = [wrapped for line in summary(match) for wrapped in (textwrap.wrap(line, width) or [""])]
    page_size = max(5, settings.display_height - 5)
    for start in range(0, len(lines), page_size):
        last = start + page_size >= len(lines)
        _frame([*lines[start:start + page_size], "'Enter' Return to menu" if last else "'Enter' Next page"], settings)
        input("After action: ")
