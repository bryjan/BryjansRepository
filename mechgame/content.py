"""Playable scenarios built from the reusable mech catalog."""

from .catalog import create_mech
from .entities import Entity, Pilot
from .teams import Squad, Team


# Keep player-facing role notes alongside the demo roster.  The help screen
# derives equipment and pilot names from the live match, while these notes
# explain why each chassis is present in the scenario.
DEMO_TACTICAL_NOTES = {
    "Lancer Type.S Pathfinder": (
        "Strengths: active radar, best Lancer vision, accurate Scout Rifle. "
        "Weakness: lighter armor and only one direct-fire weapon."
    ),
    "Lancer Type.A": (
        "Strengths: flexible ChainGun and armor-piercing Plasma Lance. "
        "Weakness: must close to 1.5 tiles to use the lance."
    ),
    "Lancer Type.M Mortar": (
        "Strengths: indirect HE, smoke, flare, and incendiary support. "
        "Weakness: limited ammunition and weak at close range."
    ),
    "Bastion": (
        "Strengths: heavy armor, sustained weapons, and one field repair. "
        "Weakness: slow, no active radar, and easy to spot."
    ),
    "Kestrel": (
        "Strengths: long-range beam, active radar, and sensor overdrive. "
        "Weakness: leg damage cuts mobility; its large reserve supports bursts, not careless spending."
    ),
}


def _weapon_loadout_text(weapon):
    """Return one concise, current equipment label for the demo briefing."""
    if weapon.isLauncher:
        ammo = ", ".join(
            f"{shell.name} {shell.charges}/{shell.maxCharges}"
            for shell in weapon.ammoTypes
        )
        return f"{weapon.name} ({ammo})"
    charges = "unlimited" if weapon.charges is None else f"{weapon.charges}/{weapon.maxCharges}"
    return f"{weapon.name} ({charges})"


def demo_roster_summary(match):
    """Build an accurate, readable roster and role briefing for ``?`` help."""
    lines = ["", "Demo roster and tactical briefing:"]
    for team in match.teamList:
        lines.append(f"{team.name}:")
        for squad in team.squadsList:
            for mech in squad.mechList:
                loadout = ", ".join(
                    _weapon_loadout_text(weapon)
                    for weapon in mech.mechClass.gunList
                )
                note = DEMO_TACTICAL_NOTES.get(
                    mech.mechClass.name,
                    "No tactical note is available for this chassis.",
                )
                lines.append(
                    f"  {mech.name} — {mech.mechClass.name}: {loadout}. {note}"
                )
    return lines


def create_demo_teams():
    """Create the playable sensor-and-artillery test match."""
    player_mechs = [
        Entity(create_mech("lancer.pathfinder"), Pilot("B")),
        Entity(create_mech("lancer.type_a"), Pilot("MagikP")),
        Entity(create_mech("lancer.type_a"), Pilot("Xactly")),
        Entity(create_mech("lancer.type_a"), Pilot("115um6uy15")),
        Entity(create_mech("lancer.mortar"), Pilot("Chiki")),
    ]
    enemy_mechs = [
        Entity(create_mech("bastion"), Pilot("Blastra")),
        Entity(create_mech("kestrel"), Pilot("UncLord")),
        Entity(create_mech("bastion"), Pilot("Sybis")),
    ]
    player = Team("Player Team", [Squad("Player Squad", player_mechs, "Combat", playerControlled=True)])
    enemies = Team("Enemy Team", [Squad("Enemy Squad", enemy_mechs, "Combat")])
    # The match begins with the player squad, so keep it first in turn order.
    # A complete round is then player turn, enemy turn, and back to player.
    return [player, enemies]
