"""Team-level staging for joint attacks using only shared enemy contacts."""

from dataclasses import dataclass, field
import math

from .formation import formation_radius


@dataclass
class CombinedAttack:
    squads: tuple
    targets: tuple
    staging_positions: dict
    created_round: int
    state: str = "staging"
    reason: str = ""
    target_positions: dict = field(default_factory=dict)
    target_forces: dict = field(default_factory=dict)
    kind: str = "stage_attack"
    target_fixes: dict = field(default_factory=dict)


def observed_fix(match, team, target):
    """Snapshot a visual fix or stored radar data; unresolved motion stays zero."""
    visual = any(target in mech.directlyVisibleEnemies for squad in team.squadsList for mech in squad.mechList)
    memory = team.radarContacts.get(target)
    if visual:
        position, start, speed, turn = tuple(target.pos), target.turnStartPos, target.speed, match.matchRound
    elif memory:
        position = tuple(memory["position"])
        start = memory["turn_start_pos"]
        speed = memory["speed"] if memory["level"] >= 3 else 0
        turn = memory.get("observed_round", match.matchRound)
    else:
        # Legacy scenario contacts may not carry a radar record yet.
        return tuple(target.pos), (0, 0), match.matchRound
    dx, dy = position[0] - start[0], position[1] - start[1]
    length = math.hypot(dx, dy)
    velocity = (dx * speed / length, dy * speed / length) if length else (0, 0)
    return position, velocity, turn


def projected_position(match, fix):
    """Lead by one round; extrapolate stale fixes for at most three rounds."""
    position, velocity, turn = fix
    horizon = min(3, max(1, match.matchRound - turn + 1))
    return tuple(max(1, min(limit - 2, round(position[i] + velocity[i] * horizon)))
                 for i, limit in enumerate((match.mapWidth, match.mapHeight)))


def waiting(squad):
    order = squad.combinedAttack
    return order is not None and order.state == "staging"


def contacts(match, team):
    """Use living contacts held by friendly observers, never enemy squads."""
    return list(dict.fromkeys(
        enemy for squad in team.squadsList for mech in squad.mechList
        for enemy in [*mech.directlyVisibleEnemies, *mech.trackedEnemies]
        if enemy in match.entities and enemy.team is not team
    ))


def order_attack(match, team, squads, targets, *, stage=False):
    """Coordinate attacks in place, or explicitly assemble first with stage=True."""
    from .ai import _entity_combat_force
    squads = tuple(dict.fromkeys(squads))
    known = contacts(match, team)
    targets = tuple(dict.fromkeys(targets))
    if len(squads) < 2 or not targets or any(target not in known for target in targets):
        raise ValueError("A combined attack needs two squads and currently known enemy targets.")
    if any(squad not in team.squadsList or squad.playerControlled or not squad.mechList
           or squad.fleeOrdered or squad.shouldLeaveBattlefield for squad in squads):
        raise ValueError("Combined attacks require operational, non-withdrawing AI squads on this team.")
    center = tuple(round(sum(squad.squadLead.pos[i] for squad in squads) / len(squads)) for i in (0, 1))
    positions = {}
    for squad in squads if stage else ():
        # Spread assembly points while retaining immediate mutual support.
        # Unknown terrain is not considered for deliberate staging positions.
        choices = [
            (x, y) for y in range(max(1, center[1] - 6), min(match.mapHeight - 1, center[1] + 7))
            for x in range(max(1, center[0] - 6), min(match.mapWidth - 1, center[0] + 7))
            if (team.mapVisibility.show_all_terrain or (x, y) in team.exploredTiles)
            and match.map[y][x].terrain.passable
            and not match.map[y][x].terrain.requireFloat
            and all(math.dist((x, y), used) >= 3 for used in positions.values())
        ]
        positions[squad] = min(choices, key=lambda pos: math.dist(pos, center), default=tuple(squad.squadLead.pos))
    order = CombinedAttack(squads, targets, positions, match.matchRound)
    order.kind = "stage_attack" if stage else "coordinated_attack"
    order.state = "staging" if stage else "attacking"
    order.target_fixes = {enemy: observed_fix(match, team, enemy) for enemy in targets}
    order.target_positions = {enemy: projected_position(match, fix) for enemy, fix in order.target_fixes.items()}
    order.target_forces = {enemy: _entity_combat_force(enemy) for enemy in targets}
    team.combinedAttacks.append(order)
    for squad in squads:
        squad.combinedAttack = order
        squad.ambushLocation = None
        squad.primaryTarget = max(targets, key=_entity_combat_force) if not stage else None
        squad.stopRoadPatrol()
        squad.setCombatPosture("engage")
        squad.setMovementPolicy(mode="move")
        squad.avoidContact = False
        for mech in squad.mechList:
            mech.approachTarget = mech.approachWeapon = None
    return order


def update(match, team):
    """Refresh orders, releasing ready squads and cancelling invalid attacks."""
    from .ai import _entity_combat_force
    known = contacts(match, team)
    for order in team.combinedAttacks:
        if order.state not in {"staging", "attacking"}:
            continue
        live_squads = [s for s in order.squads if s.mechList and not s.fleeOrdered
                       and not s.shouldLeaveBattlefield and s.combatPosture != "retreat"
                       and s.ambushLocation is None and s.combinedAttack is order]
        live_targets = [target for target in order.targets if target in known]
        friendly_force = sum(s.combatForce for s in live_squads)
        # Refresh only observed enemies. Losing a scan retains the last
        # position and force estimate instead of reading hidden movements.
        for target in live_targets:
            order.target_fixes[target] = observed_fix(match, team, target)
            order.target_forces[target] = _entity_combat_force(target)
        order.target_positions = {enemy: projected_position(match, fix) for enemy, fix in order.target_fixes.items()}
        enemy_force = sum(order.target_forces.values())
        if len(live_squads) < 2 or friendly_force < enemy_force:
            order.state = "cancelled"
            order.reason = "Insufficient participating force."
            for squad in order.squads:
                if squad.combinedAttack is order:
                    squad.combinedAttack = None
                    squad.primaryTarget = None
            continue
        if order.state == "staging":
            ready = all(
                math.dist(s.squadLead.pos, order.staging_positions[s]) <= 2
                and all(math.dist(mech.pos, s.squadLead.pos) <= formation_radius(s.squadLead)
                        and mech.energy >= mech.mechClass.energyMax * .9 for mech in s.mechList)
                for s in live_squads
            )
            if not ready and match.matchRound - order.created_round >= 5:
                order.state = "cancelled"
                order.reason = "Assembly timed out."
                for squad in order.squads:
                    if squad.combinedAttack is order:
                        squad.combinedAttack = None
                        squad.primaryTarget = None
                continue
            if not ready:
                continue
            order.state = "attacking"
        target = max(live_targets, key=_entity_combat_force, default=None)
        for squad in live_squads:
            squad.primaryTarget = target
        if target is None and all(
            min(math.dist(squad.squadLead.pos, pos) for pos in order.target_positions.values()) <= 2
            for squad in live_squads
        ):
            order.state = "complete"
            order.reason = "Last known enemy area reached without reacquiring contact."
            for squad in live_squads:
                squad.combinedAttack = None


def plan(match, team):
    """Once per round, combine smaller idle squads against an observed group."""
    update(match, team)
    if team.lastCoordinationRound == match.matchRound:
        return
    team.lastCoordinationRound = match.matchRound
    from .ai import _entity_combat_force
    from . import recon
    available = [s for s in team.squadsList if not s.playerControlled and s.mechList
                 and s.combatEffective and not s.shouldLeaveBattlefield and not s.fleeOrdered
                 and s.combinedAttack is None and s.ambushLocation is None
                 and not s.manualOrder
                 and s.investigationPosition is None and not recon.emergency(match, s)
                 and s.combatPosture in {"engage", "attack"}]
    if prefer_ambush(match, team, available):
        return
    if len(available) < 2:
        return
    known = contacts(match, team)
    for target in sorted(known, key=_entity_combat_force, reverse=True):
        group = [enemy for enemy in known if math.dist(enemy.pos, target.pos) <= 10]
        force = sum(_entity_combat_force(enemy) for enemy in group)
        candidates = sorted(
            (s for s in available if s.combatForce < force and math.dist(s.squadLead.pos, target.pos) <= 40),
            key=lambda s: math.dist(s.squadLead.pos, target.pos),
        )
        chosen = []
        for squad in candidates:
            chosen.append(squad)
            if len(chosen) >= 2 and sum(s.combatForce for s in chosen) >= force * 1.1:
                # Opposite sides: keep the existing encirclement and attack
                # together. Otherwise assemble before advancing as a group.
                between = any(
                    sum((a.squadLead.pos[i] - target.pos[i]) *
                        (b.squadLead.pos[i] - target.pos[i]) for i in (0, 1)) < 0
                    for index, a in enumerate(chosen) for b in chosen[index + 1:]
                )
                order_attack(match, team, chosen, group, stage=not between)
                return


def prefer_ambush(match, team, squads):
    """Prefer nearby known concealment overlooking a tactical approach."""
    if match.matchRound - team.lastEngagedRound <= 1:
        return False
    choices = []
    known = team.exploredTiles
    for squad in squads:
        # Assigned patrols must keep circulating, and a fixed guard must keep
        # its objective covered. Neither is an idle squad seeking an ambush.
        if getattr(squad.currentGoal, "kind", "") in {"patrol", "patrol_map", "patrol_location", "defend_location", "return_to_defend"}:
            continue
        if squad.inCombat:
            # Mere visual contact is allowed; recent damage or firing isn't.
            if any(mech.lastCombatSignal != "enemy in visual range" and mech.inCombat for mech in squad.mechList):
                continue
        for location in match.mapFeatures.tactical_locations:
            for tx, ty in location.marker_tiles or location.tiles[:1]:
                if math.dist(squad.squadLead.pos, (tx, ty)) > 15:
                    continue
                for y in range(max(1, ty - 3), min(match.mapHeight - 1, ty + 4)):
                    for x in range(max(1, tx - 3), min(match.mapWidth - 1, tx + 4)):
                        if not team.mapVisibility.show_all_terrain and (x, y) not in known:
                            continue
                        tile = match.map[y][x].terrain
                        if not tile.passable or tile.requireFloat or tile.visAbsorb < 6:
                            continue
                        if any(tile.moveCost[mech.size] > mech.mechClass.energyMax for mech in squad.mechList):
                            continue
                        # Keep distinct firing positions while allowing
                        # mutually supporting ambushes at one choke point.
                        if any(other.ambushLocation is not None and math.dist((x, y), other.ambushLocation) < 3
                               for other in team.squadsList):
                            continue
                        score = min(tile.visAbsorb, 20) - math.dist((x, y), squad.squadLead.pos) - math.dist((x, y), (tx, ty))
                        choices.append((score, squad, (x, y)))
    if not choices:
        return False
    from .ai import _entity_combat_force
    from .ambush import waiting as ambush_waiting
    enemies = contacts(match, team)
    for _, squad, position in sorted(choices, key=lambda choice: choice[0], reverse=True):
        enemy_force = sum(_entity_combat_force(enemy) for enemy in enemies
                          if math.dist(observed_fix(match, team, enemy)[0], position) <= 30)
        if enemy_force < squad.combatForce * .8:
            # With no comparable observed threat, a single squad is enough.
            if any(other.ambushLocation is not None and math.dist(position, other.ambushLocation) < 8
                   for other in team.squadsList):
                continue
            team.orderAmbush(squad, position)
            return True
        # Anchor a cluster on existing concealed squads when possible, then
        # recruit additional covered positions until the force is sufficient.
        supporting = [other for other in team.squadsList if other is not squad
                      and ambush_waiting(other) and not other.fleeOrdered
                      and other.combatEffective and other.combatPosture != "retreat"
                      and math.dist(other.ambushLocation, position) <= 12]
        selected = [(squad, position)]
        used = {squad, *supporting}
        occupied = [position, *(other.ambushLocation for other in supporting)]
        force = squad.combatForce + sum(other.combatForce for other in supporting)
        for _, recruit, site in sorted(choices, key=lambda choice: choice[0], reverse=True):
            if force >= enemy_force * 1.1 and len(used) >= 2:
                break
            if recruit in used or math.dist(position, site) > 12:
                continue
            if any(math.dist(site, taken) < 3 for taken in occupied):
                continue
            selected.append((recruit, site))
            occupied.append(site)
            used.add(recruit)
            force += recruit.combatForce
        if force < enemy_force * 1.1 or len(used) < 2:
            continue
        for member, site in selected:
            team.orderAmbush(member, site)
        group = tuple([member for member, _ in selected] + supporting)
        for member in group:
            member.ambushGroup = group
        return True
    return False
