"""Team-level staging for joint attacks using only shared enemy contacts."""

from dataclasses import dataclass, field
import math


@dataclass
class CombinedAttack:
    squads: tuple
    targets: tuple
    staging_positions: dict
    created_round: int
    state: str = "staging"
    reason: str = ""
    target_positions: dict = field(default_factory=dict)


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


def order_attack(match, team, squads, targets):
    """Stage explicitly selected AI squads before committing them together."""
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
    for squad in squads:
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
    order.target_positions = {enemy: tuple(enemy.pos) for enemy in targets}
    team.combinedAttacks.append(order)
    for squad in squads:
        squad.combinedAttack = order
        squad.ambushLocation = None
        squad.primaryTarget = None
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
        enemy_force = sum(_entity_combat_force(target) for target in live_targets)
        if len(live_squads) < 2 or not live_targets or friendly_force < enemy_force:
            order.state = "cancelled"
            order.reason = "Insufficient force or lost enemy contact."
            for squad in order.squads:
                if squad.combinedAttack is order:
                    squad.combinedAttack = None
                    squad.primaryTarget = None
            continue
        if order.state == "staging":
            ready = all(
                math.dist(s.squadLead.pos, order.staging_positions[s]) <= 2
                and all(math.dist(mech.pos, s.squadLead.pos) <= max(10, s.squadLead.visPower)
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
        target = max(live_targets, key=_entity_combat_force)
        for squad in live_squads:
            squad.primaryTarget = target


def plan(match, team):
    """Once per round, combine smaller idle squads against an observed group."""
    update(match, team)
    if team.lastCoordinationRound == match.matchRound:
        return
    team.lastCoordinationRound = match.matchRound
    from .ai import _entity_combat_force
    available = [s for s in team.squadsList if not s.playerControlled and s.mechList
                 and s.combatEffective and not s.shouldLeaveBattlefield and not s.fleeOrdered
                 and s.combinedAttack is None and s.ambushLocation is None
                 and s.combatPosture in {"engage", "attack"}]
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
                order_attack(match, team, chosen, group)
                return
