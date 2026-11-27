"""Unknown-source evasion, coarse sound bearings and stale-area reconnaissance."""

from dataclasses import dataclass
import math

from .coordinates import nesw_direction


@dataclass
class SoundContact:
    weapon: str
    direction: str
    position: tuple
    round: int


def hear_fire(match, listener, shooter, weapon):
    """Record an eight-way bearing, never the hidden gun's exact location."""
    direction = nesw_direction(listener.pos, shooter.pos)
    dx = (shooter.pos[0] > listener.pos[0]) - (shooter.pos[0] < listener.pos[0])
    dy = (shooter.pos[1] > listener.pos[1]) - (shooter.pos[1] < listener.pos[1])
    distance = min(weapon.soundReport, max(10, listener.visPower))
    length = math.hypot(dx, dy) or 1
    position = (max(1, min(match.mapWidth - 2, round(listener.pos[0] + dx * distance / length))),
                max(1, min(match.mapHeight - 2, round(listener.pos[1] + dy * distance / length))))
    squad = listener.squad
    squad.investigationPlannedRound = -1
    squad.soundContacts = [sound for sound in squad.soundContacts
                           if sound.round >= match.matchRound - 2
                           and (sound.weapon, sound.direction) != (weapon.name, direction)]
    squad.soundContacts.append(SoundContact(weapon.name, direction, position, match.matchRound))
    squad.soundContacts = squad.soundContacts[-8:]
    listener.team.searchUntilRound = max(listener.team.searchUntilRound, match.matchRound + 3)
    if listener.mechClass.shareData:
        listener.team.heardFireContacts = [sound for sound in listener.team.heardFireContacts
                                         if sound.round >= match.matchRound - 2
                                         and (sound.weapon, sound.direction) != (weapon.name, direction)]
        listener.team.heardFireContacts.append(squad.soundContacts[-1])
        listener.team.heardFireContacts = listener.team.heardFireContacts[-8:]
        listener.team.searchFocus = position
    return direction


def unknown_damage(match, defender, attacker):
    """Start an evasion/search response only from genuinely unknown hostile hits."""
    team = defender.team
    attacking_team = getattr(attacker, "team", attacker)
    if attacking_team is team:
        return
    if attacker is not None and any(
        attacker in mech.directlyVisibleEnemies
        for squad in team.squadsList for mech in squad.mechList
    ):
        return
    memory = team.radarContacts.get(attacker)
    if memory is not None and memory["level"] >= 3:
        return
    squad = defender.squad
    if squad.unknownThreatRound != match.matchRound:
        squad.unknownThreatPositions.clear()
    squad.unknownThreatRound = match.matchRound
    squad.investigationPlannedRound = -1
    squad.unknownThreatSerial += 1
    squad.unknownThreatPositions[defender] = tuple(defender.pos)
    team.searchUntilRound = max(team.searchUntilRound, match.matchRound + 5)
    team.searchFocus = tuple(defender.pos)
    defender.report(match, "Taking damage from an unknown source: reposition and investigate firing sounds or unseen areas.", critical=True)


def emergency(match, squad):
    return (match.matchRound - squad.unknownThreatRound <= 2 and any(
        mech.unknownEvadeSerial < squad.unknownThreatSerial and mech.mechClass.mpMax > 0
        for mech in squad.mechList))


def latest_sound(match, squad):
    local = next((sound for sound in reversed(squad.soundContacts)
                 if match.matchRound - sound.round <= 2), None)
    return local or next((sound for sound in reversed(squad.team.heardFireContacts)
                          if match.matchRound - sound.round <= 2), None)


def oldest_area(match, squad, focus=None):
    """Compare six-tile areas by their average last visual observation round."""
    leader, team = squad.squadLead, squad.team
    focus = focus or tuple(leader.pos)
    candidates = []
    for y in range(max(1, focus[1] - 24), min(match.mapHeight - 1, focus[1] + 25), 6):
        for x in range(max(1, focus[0] - 24), min(match.mapWidth - 1, focus[0] + 25), 6):
            cells = [(cx, cy) for cy in range(y, min(y + 6, match.mapHeight - 1))
                     for cx in range(x, min(x + 6, match.mapWidth - 1))]
            if not cells or all(pos in team.sharedVisibleTiles for pos in cells):
                continue
            center = (min(x + 3, match.mapWidth - 2), min(y + 3, match.mapHeight - 2))
            stale = [pos for pos in cells if pos not in team.sharedVisibleTiles
                     and team.lastSeenRound.get(pos, -1) < match.matchRound]
            if not stale:
                continue
            point = min(stale, key=lambda pos: (team.lastSeenRound.get(pos, -1), math.dist(pos, center)))
            if point in team.exploredTiles or team.mapVisibility.show_all_terrain:
                terrain = match.map[point[1]][point[0]].terrain
                if not terrain.passable or terrain.requireFloat and not (leader.flying or leader.mechClass.canFloat or leader.size == 6):
                    continue
            if any(math.dist(point, position) < 6 for position, until in team.pendingScoutAreas
                   if until >= match.matchRound):
                continue
            age = sum(team.lastSeenRound.get(pos, -1) for pos in cells) / len(cells)
            candidates.append((age, math.dist(point, focus), math.dist(point, leader.pos), point))
    return min(candidates)[-1] if candidates else None


def prepare(match, squad):
    """Plan once per squad/round; search roles investigate stale visual coverage."""
    if any(enemy in match.entities for mech in squad.mechList for enemy in mech.directlyVisibleEnemies):
        squad.investigationPosition = None
        return
    if squad.investigationPlannedRound == match.matchRound:
        return
    squad.investigationPlannedRound = match.matchRound
    squad.investigationPosition = None
    if squad.fleeOrdered or squad.combatPosture in {"retreat", "stealth", "hold_fire"}:
        return
    sound = latest_sound(match, squad)
    # Explicit player orders retain priority except immediate evasion.
    if squad.manualOrder:
        return
    if getattr(squad.currentGoal, "kind", "") in {"return_to_defend", "reinforce"}:
        # A recall is more urgent than investigating a sound or stale area.
        # Immediate evasive movement is still handled separately.
        return
    if sound is not None:
        squad.investigationPosition = sound.position
        return
    suitable = any(any(mech.roleReadiness.get(role, 0) >= 60 for role in ("scout", "sensor", "skirmisher"))
                   for mech in squad.mechList)
    searching = match.matchRound <= squad.team.searchUntilRound
    if suitable and (searching or (getattr(squad.currentGoal, "kind", "") == "eliminate_enemies"
                                  and squad.movementBehavior != "road_patrol")):
        focus = squad.team.searchFocus if searching else (
            squad.currentGoal.locations[0] if squad.currentGoal and squad.currentGoal.locations else None)
        squad.investigationPosition = oldest_area(match, squad, focus)


def reposition(match, squad):
    """Leave suspected impact cells before normal fighting or formation holds."""
    from .ai import _legal_steps
    moved = []
    sound = latest_sound(match, squad)
    impacts = list(squad.unknownThreatPositions.values())
    if squad.ambushLocation is not None and not squad.ambushTriggered:
        squad.releaseAmbush()
    squad.combinedAttack = None
    for mech in list(squad.mechList):
        if mech.unknownEvadeSerial >= squad.unknownThreatSerial:
            continue
        start = tuple(mech.pos)
        visited = {start}
        for _ in range(3):
            choices = [(position, energy) for position, energy in _legal_steps(match, mech, "double_time")
                       if tuple(position) not in visited and math.dist(position, start) > math.dist(mech.pos, start)]
            if not choices:
                break
            position, _ = max(choices, key=lambda item: (
                min(4, min((math.dist(item[0], hit) for hit in impacts), default=4)),
                -math.dist(item[0], sound.position) if sound is not None else -item[1],
                math.dist(item[0], start),
            ))
            if not mech.moveTo(match, position, announce=False):
                break
            visited.add(tuple(position))
            moved.append(mech)
            if mech.destroyed:
                break
        if tuple(mech.pos) != start or mech.mechClass.mpMax <= 0:
            mech.unknownEvadeSerial = squad.unknownThreatSerial
    return moved


def scout_fire(match, squad):
    """Use one scouting payload per team every two rounds while searching."""
    team = squad.team
    if squad.manualOrder or match.matchRound > team.searchUntilRound or match.matchRound - team.lastScoutFireRound < 2:
        return set()
    focus = squad.investigationPosition
    if focus is None:
        sounds = [latest_sound(match, other) for other in team.squadsList]
        sound = next((sound for sound in sounds if sound is not None), None)
        focus = sound.position if sound else None
    point = oldest_area(match, squad, focus)
    if point is None:
        return set()
    for mech in squad.mechList:
        for weapon in mech.mechClass.gunList:
            if not weapon.isLauncher or weapon.hp <= 0 or mech.ap < weapon.apCost or mech.energy < weapon.energyCost:
                continue
            for index, ammo in enumerate(weapon.ammoTypes):
                if ammo.payload != "scout" or ammo.charges == 0:
                    continue
                profile = ammo.profile(math.dist(mech.pos, point), weapon.launcher_range_bonus(match, mech))
                if profile is None:
                    continue
                previous = weapon.selectedAmmoIndex
                weapon.select_ammo(index)
                fired = weapon.launchAt(match, list(point), shooter=mech)
                weapon.select_ammo(previous)
                if fired:
                    team.lastScoutFireRound = match.matchRound
                    team.pendingScoutAreas = [(pos, until) for pos, until in team.pendingScoutAreas if until >= match.matchRound]
                    team.pendingScoutAreas.append((point, match.matchRound + profile["turns"] + ammo.effectTurns + 1))
                    return {mech}
    return set()
