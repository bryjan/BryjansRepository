"""One-squad reinforcement requests, AI responses and player notifications."""

import math

EVEN_FORCE_RATIO = .9
SUPPORT_PRIORITY = 200
COMMITTED_ATTACKS = {"attack", "attack_military_base"}
DIRECT_ROLES = {"combat", "front_line", "anchor", "assault", "skirmisher", "anti_heavy", "anti_swarm"}


def _record(recipient, sender):
    return next((item for item in recipient.supportRequests
                 if item.kind == "Reinforcements" and item.sender is sender), None)


def request(match, sender, recipient):
    """Refresh a location snapshot; notify manual players once per active call."""
    if sender.squadLead is None:
        return
    from .objectives import request_support
    previous = _record(recipient, sender)
    notify = previous is None or previous.status(match) != "Active"
    recipient.reinforcementRequest = sender
    request_support(match, sender, recipient, "Reinforcements", sender.squadLead.pos,
                    "Support this squad at its reported location; it may continue retreating while you approach.")
    if notify:
        recipient.logAI(match, f"Reinforcement request from {sender.name} at {sender.squadLead.pos}.")
        if recipient.playerCommandable and recipient.squadLead is not None:
            recipient.squadLead.report(match, f"Reinforcement request from {sender.name} squad.", critical=True)
    if not recipient.playerControlled:
        prepare(match, recipient)


def _available(squad):
    if (not squad.mechList or not squad.combatEffective or squad.shouldLeaveBattlefield
            or squad.fleeOrdered or squad.avoidContact or squad.inCombat
            or squad.combatPosture in {"retreat", "stealth", "hold_fire", "attack"}
            or squad.combinedAttack is not None or squad.reinforcementRequest is not None
            or squad.manualOrder and not squad.playerControlled
            or getattr(squad.currentGoal, "kind", "") in COMMITTED_ATTACKS | {"defend_location"}):
        return False
    # Preserve the raid's fixed base guard, even after its recall is queued.
    if any(goal.kind == "defend_location" and goal.objective_id == "raid_base" for goal in squad.currentGoals):
        return False
    return any(any(mech.roleReadiness.get(role, 0) >= 60 for role in DIRECT_ROLES) for mech in squad.mechList)


def consider(match, squad, contacts):
    """Ask one available ally when losing or facing roughly equal local force."""
    if squad.playerControlled or squad.squadLead is None or squad.reinforcementRequest is not None:
        return None
    from .ai import _entity_combat_force
    from .radar import contact_position
    local = [target for target in contacts if target in match.entities
             and math.dist(squad.squadLead.pos, contact_position(squad.squadLead, target))
             <= max(20, squad.squadLead.visPower)]
    losing = squad.inCombat and squad.engagementAssessment == "unfavorable"
    equal_or_greater = bool(local) and sum(_entity_combat_force(target) for target in local) >= squad.combatForce * EVEN_FORCE_RATIO
    if not losing and not equal_or_greater:
        return None
    for other in squad.team.squadsList:
        if other.reinforcementRequest is not None:
            prepare(match, other)
    # Renew the same helper rather than pulling another squad every turn.
    helper = next((other for other in squad.team.squadsList
                   if other.reinforcementRequest is squad and other.mechList
                   and not other.fleeOrdered and not other.shouldLeaveBattlefield
                   and not other.avoidContact and other.combatPosture != "retreat"), None)
    if helper is None:
        candidates = [other for other in squad.team.squadsList if other is not squad and _available(other)]
        helper = min(candidates, key=lambda other: (
            math.dist(squad.squadLead.pos, other.squadLead.pos), -other.combatForce,
        ), default=None)
    if helper is not None:
        request(match, squad, helper)
    return helper


def prepare(match, squad):
    """Move an AI helper to the caller; release it when the call expires."""
    sender = squad.reinforcementRequest
    if sender is None:
        return
    record = _record(squad, sender)
    goal_id = "reinforcement_response"
    explicit_attack = getattr(squad.currentGoal, "kind", "") in COMMITTED_ATTACKS
    unavailable = (squad.fleeOrdered or squad.shouldLeaveBattlefield or squad.avoidContact
                   or squad.combatPosture == "retreat"
                   or not squad.playerControlled and (squad.manualOrder or explicit_attack))
    if (record is None or record.status(match) != "Active" or not sender.mechList
            or not squad.mechList or unavailable):
        if record is not None:
            record.dismissed = True
        squad.reinforcementRequest = None
        squad.currentGoals = [goal for goal in squad.currentGoals if goal.goal_id != goal_id]
        if getattr(squad.currentGoal, "goal_id", "") == goal_id:
            squad.currentGoal = max(squad.currentGoals, key=lambda goal: goal.priority, default=None)
            squad._refreshOperationalFlags()
        squad.logAI(match, "Reinforcement response ended; resume standing orders.")
        return
    if squad.playerControlled:
        return
    from .ai import SquadGoal
    goal = SquadGoal(goal_id, "reinforcement_response", "reinforce", SUPPORT_PRIORITY,
                     (record.position,), f"Support {sender.name} at its last reported friendly position.")
    previous = next((item for item in squad.currentGoals if item.goal_id == goal_id), None)
    squad.currentGoals = [item for item in squad.currentGoals if item.goal_id != goal_id]
    squad.currentGoals.insert(0, goal)
    squad.currentGoal = goal
    squad.stopRoadPatrol()
    squad.ambushLocation = None
    squad.ambushGroup = ()
    squad.investigationPosition = None
    squad.setMovementPolicy(mode="move", behavior="formation")
    if previous is None:
        squad.goalHistory.append(goal)
        squad.logAI(match, f"Order: reinforce {sender.name} at {record.position}.")
    squad._refreshOperationalFlags()
