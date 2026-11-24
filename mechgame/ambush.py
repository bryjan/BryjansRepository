"""Quiet squad positioning and cheap, observed-contact ambush triggers."""

import copy
import math


def waiting(squad):
    return squad.ambushLocation is not None and not squad.ambushTriggered


def update(match, squad):
    """Spring at peak direct damage, or as a near miss starts withdrawing.

    Sample the straight approach to each visually confirmed contact. Use the
    strongest mech/weapon's fresh-turn damage, and the farthest sampled cell
    delivering 95% of that peak as its effective distance. This shares the
    normal armor, accuracy, AP, energy and ammunition calculator.
    """
    from .ai import _known_targets, _weapon_damage_per_turn

    if not waiting(squad) or squad.fleeOrdered or squad.combatPosture == "retreat":
        return
    for mech in squad.mechList:
        mech.radarOn = mech.radarPulseActive = False
        mech.approachTarget = mech.approachWeapon = None
    if squad.damageReceived > squad.ambushDamageBaseline:
        squad.releaseAmbush()
        return
    if squad.ambushWaitForOrder:
        return
    visible = {
        target for mech in squad.mechList for target in mech.directlyVisibleEnemies
        if target in match.entities and target.team is not squad.team
    }
    candidates = []
    for mech in squad.mechList:
        for target in _known_targets(mech):
            if target not in visible:
                continue
            distance = math.dist(mech.pos, target.pos)
            for weapon in mech.mechClass.gunList:
                if weapon.isLauncher or weapon.hp <= 0 or weapon.charges == 0:
                    continue
                samples = []
                preview = copy.copy(mech)
                preview.ap = mech.mechClass.apMax
                preview.speed = 0
                # One sample per tile along the observed approach; bounded
                # by contact distance, with no pathfinding or extra scans.
                for step in range(max(1, math.ceil(distance))):
                    fraction = step / max(1, math.ceil(distance))
                    preview.pos = [round(mech.pos[i] + (target.pos[i] - mech.pos[i]) * fraction) for i in (0, 1)]
                    reach = math.dist(preview.pos, target.pos)
                    if reach == 0 or weapon.maxRange is not None and reach > weapon.maxRange:
                        continue
                    dps, _ = _weapon_damage_per_turn(match, preview, target, weapon)
                    samples.append((dps, reach))
                peak = max((dps for dps, _ in samples), default=0)
                if peak <= 0:
                    continue
                effective_range = max(reach for dps, reach in samples if dps >= peak * .95)
                candidates.append((peak, mech, target, distance, effective_range))
    if not candidates:
        squad.ambushDistances = {}
        return
    _, mech, target, distance, effective_range = max(candidates, key=lambda item: item[0])
    previous = squad.ambushDistances.get((mech, target))
    near_then_receding = previous is not None and previous <= effective_range + 2 and distance > previous
    if distance <= effective_range or near_then_receding:
        squad.releaseAmbush()
    # Only retain currently observed pairs; no tracking through lost contact.
    squad.ambushDistances = {(unit, enemy): dist for _, unit, enemy, dist, _ in candidates}
    squad.ambushMech = mech
    squad.ambushTarget = target
    squad.ambushEffectiveRange = effective_range
