"""Validated player orders for friendly AI squads."""

def set_control(squad, ai):
    if not squad.playerCommandable:
        raise ValueError("Only player-owned squads can change control.")
    if ai and squad.playerControlled and not any(
        other is not squad and other.playerCommandable and other.playerControlled and other.mechList
        for other in squad.team.squadsList
    ):
        raise ValueError("At least one surviving squad must remain player controlled.")
    squad.playerControlled = not ai
    squad.autoTravelEnabled = False


def issue(match, squad, kind, position=None, target=None):
    from .ai import SquadGoal
    if not squad.playerCommandable or not squad.mechList:
        raise ValueError("Choose a live friendly squad.")
    if squad.playerControlled:
        raise ValueError("Delegate this squad to AI before giving it AI orders.")
    if kind not in {"move", "defend", "patrol", "attack", "ambush", "retreat", "flee", "hold"}:
        raise ValueError("Unknown squad order.")
    if kind == "attack":
        from .coordination import contacts
        if target not in contacts(match, squad.team):
            raise ValueError("Attack orders require a known enemy contact.")
        from .coordination import observed_fix
        position = observed_fix(match, squad.team, target)[0]
    if kind in {"hold", "flee"}:
        position = tuple(squad.squadLead.pos)
    if position is None or not (0 <= position[0] < match.mapWidth and 0 <= position[1] < match.mapHeight):
        raise ValueError("Choose an in-bounds location.")
    squad.manualOrder = True
    squad.combinedAttack = None
    squad.ambushLocation = None
    squad.fleeOrdered = False
    squad.autoTravelEnabled = False
    squad.stopRoadPatrol()
    squad.avoidContact = False
    squad.avoidanceTarget = None
    squad.primaryTarget = target
    squad.manualAttackTarget = target
    squad.manualAttackPosition = tuple(position) if target is not None else None
    squad.setMovementPolicy(mode="move")
    squad.setCombatPosture("attack" if kind == "attack" else "retreat" if kind == "retreat" else "engage")
    goal_kind = {"hold": "defend_location", "defend": "defend_location", "patrol": "patrol_location"}.get(kind, kind)
    goal = SquadGoal("player_order", "player_order", goal_kind, 1000,
                     (tuple(position),), f"Player order: {kind}.")
    squad.currentGoal = goal
    squad.currentGoals = [goal]
    squad.goalHistory.append(goal)
    for mech in squad.mechList:
        mech.approachTarget = mech.approachWeapon = None
    if kind == "ambush":
        squad.beginAmbush(position)
    elif kind == "flee":
        squad.orderFlee()
    return goal
