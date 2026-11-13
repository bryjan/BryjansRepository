"""Radar scanning, detection, contact sharing, and reporting.

Radar functions accept match and entity objects rather than importing their
classes. This keeps the sensing system independent of unit construction and
avoids circular imports between the game-domain modules.
"""

import heapq
import math

from .coordinates import nesw_direction

# A fixed baseline makes a larger signature easier, rather than harder, to
# find.  The larger scale leaves room for low-observable units to matter.
RADAR_DETECTION_BASE = 400

# Radar travels one map cell at a time.  Open ground has an absorption of one,
# so its total loss is two power per tile: one for distance and one for terrain.
RADAR_DISTANCE_LOSS = 1


def entity_detection_threshold(radar_signature):
    """Return the radar power required to obtain a contact on an entity.

    A high radar signature reflects more energy and therefore lowers the power
    required for detection. Terrain keeps its separate radar-return values.
    """
    return max(1, RADAR_DETECTION_BASE - radar_signature)


def detection_level(radar_power, target):
    """Convert a radar return into contact, classification, or ID detail."""
    threshold = entity_detection_threshold(target.radarSig)
    if radar_power >= threshold * 2:
        return 3
    if radar_power >= threshold * 1.5:
        return 2
    if radar_power >= threshold:
        return 1
    return 0


def radar_step_loss(terrain_absorption):
    """Return the power lost while radar crosses one terrain cell."""
    return RADAR_DISTANCE_LOSS + int(terrain_absorption)


def clear_returns(match_info, invalidate=True):
    """Clear cached radar values from every map cell.

    Ordinary visual information deliberately remains intact because radar can
    be toggled without ending a squad's visual observation.
    """
    for row in match_info.map:
        for cell in row:
            cell.radarReturn = False
            cell.radarPower = 0
    if invalidate:
        match_info._radarSourceState = None


def refresh(match_info):
    """Rebuild active scans only after a meaningful source-state change."""
    sources = [
        entity
        for entity in match_info.entities
        if entity.radarOn and entity.mechClass.radarPower > 0
    ]
    source_state = tuple(
        (
            id(entity),
            tuple(entity.pos),
            entity.speed,
            entity.mechClass.radarPower,
        )
        for entity in sources
    )
    if source_state == match_info._radarSourceState:
        return

    # A rebuild combines friendly emissions and retains the strongest return
    # at a cell, rather than discarding one scanner's useful coverage.
    clear_returns(match_info, invalidate=False)
    for team in match_info.teamList:
        for squad in team.squadsList:
            squad.radarTrackedEnemies = []
    for source in sources:
        project_scan(source, match_info)
    for entity in match_info.entities:
        refresh_tracked_enemies(entity)
    match_info._radarSourceState = source_state


def project_scan(source, match_info):
    """Project one active scan through terrain using the strongest path.

    The priority queue lets a cell be revisited only when a stronger route
    reaches it, making terrain absorption meaningful without repeated broad
    full-map calculations.
    """
    game_map = match_info.map
    starting_cell = game_map[source.pos[1]][source.pos[0]]
    source_power = int(source.mechClass.radarPower / (1 + (source.speed * .25)))
    if source_power <= 0:
        return

    propagation_cutoff = 25
    best_power = {tuple(starting_cell.pos): source_power}
    frontier = [(-source_power, 0, starting_cell)]
    sequence = 1
    source.radarPower = source_power
    source.radarIDlist = [starting_cell]

    while frontier:
        negative_power, _, cell = heapq.heappop(frontier)
        power = -negative_power
        if power != best_power.get(tuple(cell.pos)):
            continue

        cell.radarPower = max(cell.radarPower, power)
        cell.radarReturn = True

        for neighbor in cell.nList:
            next_power = power - radar_step_loss(neighbor.radarAbsorption)
            neighbor_pos = tuple(neighbor.pos)
            if next_power < propagation_cutoff or next_power <= best_power.get(neighbor_pos, -1):
                continue
            best_power[neighbor_pos] = next_power
            heapq.heappush(frontier, (-next_power, sequence, neighbor))
            sequence += 1

    radar_contacts = []
    for target in match_info.entities:
        contact_power = best_power.get(tuple(target.pos), 0)
        if target.mechClass.passiveRadar and contact_power >= propagation_cutoff:
            if target.team != source.team:
                passive_detect(target, match_info, source)
        if contact_power >= entity_detection_threshold(target.radarSig):
            if target.team != source.team:
                radar_contacts.append(target)
                remember_contact(source.team, target, contact_power)
                record_contact_report(source, match_info, contact_power, target)

    # Contacts belong to the whole squad, not solely to the emitting mech.
    for contact in radar_contacts:
        if contact not in source.squad.radarTrackedEnemies:
            source.squad.radarTrackedEnemies.append(contact)


def refresh_tracked_enemies(entity):
    """Combine a mech's line-of-sight targets with squad radar contacts."""
    radar_contacts = getattr(entity.squad, "radarTrackedEnemies", [])
    team_contacts = list(getattr(entity.team, "radarContacts", {}))
    entity.trackedEnemies = list(
        dict.fromkeys([*entity.directlyVisibleEnemies, *radar_contacts, *team_contacts])
    )


def passive_detect(detector, match_info, emitter):
    """Report an enemy active scan to a stationary passive-radar detector."""
    if detector.team.name == emitter.team.name or detector.speed > 1:
        return
    if not detector.mechClass.passiveRadar:
        return

    strength = match_info.map[detector.pos[1]][detector.pos[0]].radarPower
    if strength < 50:
        return

    threshold = entity_detection_threshold(detector.radarSig)
    if strength >= threshold * 2:
        status = "identified"
    elif strength >= threshold:
        status = "noticeable"
    else:
        status = "undetected"

    direction = nesw_direction(detector.pos, emitter.pos)
    detector.report(
        match_info,
        f"Getting pinged from the {direction}. At {strength} strength, I'm {status}.",
        critical=status != "undetected",
    )


def record_contact_report(source, match_info, radar_power, target):
    """Add the most detailed report that the scan strength supports."""
    threshold = entity_detection_threshold(target.radarSig)
    if radar_power < threshold:
        return

    moving = ", not moving" if target.speed == 0 else (
        f", moving {nesw_direction(target.turnStartPos, target.pos)}"
    )
    size = "Unknown"
    identity = ""
    speed = ""
    if radar_power >= threshold * 1.5:
        size = target.sizeStr.capitalize()
    if radar_power >= threshold * 2:
        identity = f" Identified as {target.mechClass.name},"
        speed = f" Moving at {target.speed} units a turn."

    source.report(
        match_info,
        f"{size} sized object detected on radar!{identity} At {target.pos}{moving}.{speed}",
        critical=True,
    )


def team_contacts(observer):
    """Return unique team radar contacts nearest to ``observer`` first.

    Squads own their contact lists because radar data is shared locally during
    play. The radar menu combines those lists at display time so it can show
    the player's whole team's picture without duplicating contact state.
    """
    contacts = [
        contact
        for contact in getattr(observer.team, "radarContacts", {})
        if contact.team != observer.team and not contact.destroyed
    ]
    return sorted(
        contacts,
        key=lambda contact: math.dist(observer.pos, contact_position(observer, contact)),
    )


def remember_contact(team, target, radar_power):
    """Keep the strongest detection level for one target this match round."""
    level = detection_level(radar_power, target)
    previous = team.radarContacts.get(target)
    if previous is None or level > previous["level"] or (
        level == previous["level"] and radar_power > previous["radar_power"]
    ):
        team.radarContacts[target] = {
            "level": level,
            "radar_power": radar_power,
            "position": list(target.pos),
            # Save movement data with the contact. Reading it from the live
            # entity later would reveal movement after radar lost the target.
            "speed": target.speed,
            "turn_start_pos": list(target.turnStartPos),
        }


def contact_position(observer, target):
    """Return a visible target's live position or a radar contact's last fix."""
    if target in observer.directlyVisibleEnemies:
        return list(target.pos)
    memory = getattr(observer.team, "radarContacts", {}).get(target)
    return list(memory["position"]) if memory else list(target.pos)


def contact_details(observer, match_info, target):
    """Return player-facing detail for one radar contact without omniscience."""
    memory = getattr(observer.team, "radarContacts", {}).get(target)
    radar_power = memory["radar_power"] if memory else (
        match_info.map[target.pos[1]][target.pos[0]].radarPower
    )
    threshold = entity_detection_threshold(target.radarSig)
    directly_visible = target in observer.directlyVisibleEnemies
    level = memory["level"] if memory else detection_level(radar_power, target)
    identified = directly_visible or level >= 3
    size_known = identified or level >= 2
    position = contact_position(observer, target)

    if identified:
        classification = target.mechClass.name
    elif size_known:
        classification = f"{target.sizeStr.capitalize()}-class contact"
    else:
        classification = "Unclassified contact"

    if identified and directly_visible:
        movement = "stationary" if target.speed == 0 else (
            f"moving {nesw_direction(target.turnStartPos, target.pos)} "
            f"at {target.speed} tiles/turn"
        )
    elif identified and memory:
        speed = memory["speed"]
        movement = "stationary" if speed == 0 else (
            f"moving {nesw_direction(memory['turn_start_pos'], position)} "
            f"at {speed} tiles/turn (last scan)"
        )
    else:
        movement = "unresolved"

    return {
        "classification": classification,
        "position": position,
        "distance": math.dist(observer.pos, position),
        "return_power": radar_power,
        "threshold": threshold,
        "movement": movement,
        "visually_confirmed": directly_visible,
    }


def can_aim_at_contact(observer, match_info, target):
    """Return whether sensors resolve individual mech parts well enough to aim.

    A visual sighting always resolves limbs. Radar must reach the highest
    contact level—twice the target's detection threshold—before it is precise
    enough to support deliberately aiming at a specific limb.
    """
    if target in observer.directlyVisibleEnemies:
        return True
    memory = getattr(observer.team, "radarContacts", {}).get(target)
    if memory:
        return memory["level"] >= 3
    radar_power = match_info.map[target.pos[1]][target.pos[0]].radarPower
    return detection_level(radar_power, target) >= 3
