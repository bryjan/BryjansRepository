"""Player-plotted artillery orders, executed during the owning AI squad turn."""

from dataclasses import dataclass
import math


@dataclass
class FireMission:
    shooter: object
    weapon: object
    ammo_index: int
    position: tuple


def ammunition(weapon):
    """Count rounds in every selectable payload, treating unlimited as infinite."""
    return sum(float("inf") if ammo.charges is None else ammo.charges for ammo in weapon.ammoTypes)


def artillery_units(squad):
    """Prefer the operational artillery mech carrying the most total rounds."""
    return sorted(
        (mech for mech in squad.mechList if any(
            weapon.isLauncher and weapon.hp > 0 and ammunition(weapon) > 0
            for weapon in mech.mechClass.gunList)),
        key=lambda mech: sum(ammunition(weapon) for weapon in mech.mechClass.gunList
                             if weapon.isLauncher and weapon.hp > 0), reverse=True,
    )


def queue(match, mech, weapon, position):
    squad = mech.squad
    if not squad.playerCommandable or squad.playerControlled:
        raise ValueError("Fire missions require a friendly AI-controlled squad.")
    if squad.fleeOrdered or squad.combatPosture in {"retreat", "stealth", "hold_fire"}:
        raise ValueError("Change the squad's retreat/stealth/hold-fire order before requesting fire.")
    if weapon not in mech.mechClass.gunList or not weapon.isLauncher or weapon.hp <= 0:
        raise ValueError("Select an operational launcher.")
    reserved = [order for order in squad.fireMissions if order.shooter is mech]
    ammo_reserved = sum(order.weapon is weapon and order.ammo_index == weapon.selectedAmmoIndex for order in reserved)
    if weapon.selected_ammo.charges is not None and weapon.selected_ammo.charges <= ammo_reserved:
        raise ValueError("The selected ammunition is empty.")
    if sum(order.weapon.apCost for order in reserved) + weapon.apCost > mech.mechClass.apMax:
        raise ValueError("No AP remains for more queued shots. Switch artillery unit or cancel.")
    if sum(order.weapon.energyCost for order in reserved) + weapon.energyCost > mech.mechClass.energyMax:
        raise ValueError("Not enough energy capacity for more queued shots.")
    if not (0 < position[0] < match.mapWidth - 1 and 0 < position[1] < match.mapHeight - 1):
        raise ValueError("Choose a playable impact location.")
    if weapon.launcher_profile(math.dist(mech.pos, position), match, mech) is None:
        raise ValueError("The selected ammunition cannot reach that location.")
    # Retain every plotted round, including different payloads and locations.
    squad.fireMissions.append(FireMission(mech, weapon, weapon.selectedAmmoIndex, tuple(position)))
    squad.manualOrder = True
    squad.combinedAttack = None
    squad.ambushLocation = None
    print(f"Fire mission queued for {mech.pilot.display_name} at {list(position)} on {squad.name}'s next turn.")
    return True


def execute(match, squad):
    """Resolve each plotted shot once using real turn resources and launch timing."""
    handled = set()
    orders, squad.fireMissions = squad.fireMissions, []
    for order in orders:
        mech, weapon = order.shooter, order.weapon
        if mech not in squad.mechList or mech not in match.entities:
            continue
        handled.add(mech)
        if squad.fleeOrdered or squad.combatPosture in {"retreat", "stealth", "hold_fire"}:
            mech.report(match, "Fire mission cancelled by the squad's current posture.", critical=True)
            continue
        if weapon.hp <= 0 or weapon not in mech.mechClass.gunList or order.ammo_index >= len(weapon.ammoTypes):
            mech.report(match, "Fire mission cancelled: launcher unavailable.", critical=True)
            continue
        weapon.select_ammo(order.ammo_index)
        if not weapon.launchAt(match, list(order.position), shooter=mech):
            mech.report(match, "Fire mission could not fire: check ammo, AP, energy and range.", critical=True)
    return handled
