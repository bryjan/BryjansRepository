"""Renew fire support for equal/losing contacts without tracking hidden motion."""

import math

from .objectives import request_support
from .reinforcements import EVEN_FORCE_RATIO


def _can_support(match, squad, position):
    from .ai import _fire_suppressed
    if not squad.mechList or squad.fleeOrdered or squad.avoidContact or _fire_suppressed(squad):
        return False
    return any(
        weapon.hp > 0 and weapon.isLauncher
        and weapon.apCost <= mech.mechClass.apMax and weapon.energyCost <= mech.mechClass.energyMax
        and any(ammo.payload in {"explosive", "incendiary"}
                and (ammo.charges is None or ammo.charges > 0)
                and ammo.profile(math.dist(mech.pos, position), weapon.launcher_range_bonus(match, mech)) is not None
                for ammo in weapon.ammoTypes)
        for mech in squad.mechList for weapon in mech.mechClass.gunList
    )


def update(match, sender):
    """Refresh one shot per supporting unit's turn until combat turns favorable."""
    from .ai import _entity_combat_force, _known_targets, _notify_player_support_request
    from .radar import contact_details, contact_position
    from .ambush import waiting
    previous = [request for squad in sender.team.squadsList for request in squad.supportRequests
                if request.kind == "Artillery" and request.sender is sender and not request.dismissed]
    contacts = list(dict.fromkeys(target for mech in sender.mechList for target in _known_targets(mech)))
    local = [target for target in contacts if math.dist(
        sender.squadLead.pos, contact_position(sender.squadLead, target)) <= max(20, sender.squadLead.visPower)] if sender.squadLead else []
    equal_force = bool(local) and sum(_entity_combat_force(target) for target in local) >= sender.combatForce * EVEN_FORCE_RATIO
    assessment = sender.engagementAssessment
    continuing = bool(previous) and not contacts and assessment == "unassessed"
    wanted = (sender.inCombat and sender.squadLead is not None and assessment != "favorable"
              and sender.combatPosture not in {"stealth", "hold_fire"} and not waiting(sender)
              and (assessment in {"unclear", "unfavorable"} or equal_force or continuing))
    target, position, label = None, None, "last reported enemy contact"
    if wanted and contacts:
        target = max(local or contacts, key=_entity_combat_force)
        # This is a call-time snapshot. It never follows an unseen target.
        detail = contact_details(sender.squadLead, match, target)
        position, label = tuple(detail["position"]), detail["classification"]
    elif wanted and previous:
        latest = max(previous, key=lambda item: item.round)
        target, position = latest.target, latest.position
    for recipient in sender.team.squadsList:
        prior = next((item for item in recipient.supportRequests
                      if item.kind == "Artillery" and item.sender is sender and not item.dismissed), None)
        busy = (recipient.artilleryCallTurns > 0 and recipient.artilleryCallSource is not None
                and recipient.artilleryCallSource is not sender)
        valid = (wanted and target is not None and target in match.entities and not target.destroyed
                 and position is not None and not busy and _can_support(match, recipient, position))
        if not valid:
            if recipient.artilleryCallSource is sender:
                recipient.artilleryCallTarget = recipient.artilleryCallPosition = recipient.artilleryCallSource = None
                recipient.artilleryCallTurns = 0
            for item in recipient.supportRequests:
                if item.kind == "Artillery" and item.sender is sender:
                    item.dismissed = True
            continue
        notify = prior is None or prior.status(match) != "Active"
        for item in recipient.supportRequests:
            if item.kind == "Artillery" and item.sender is sender and item.target is not target:
                item.dismissed = True
        recipient.artilleryCallTarget = target
        recipient.artilleryCallPosition = position
        recipient.artilleryCallSource = sender
        recipient.artilleryCallTurns = 1
        request_support(match, sender, recipient, "Artillery", position,
                        f"Ongoing equal/losing engagement. Target: {label}. "
                        "Renew fire support while combat continues; retain lead and friendly-blast safety.", target)
        if notify:
            _notify_player_support_request(match, recipient, f"Artillery request from {sender.name} squad: engage {label}.")


def clear_shot(squad):
    """Consume the turn's firing instruction; the caller renews it next turn."""
    squad.artilleryCallTarget = squad.artilleryCallPosition = squad.artilleryCallSource = None
    squad.artilleryCallTurns = 0
