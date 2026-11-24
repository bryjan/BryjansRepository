"""Delayed launcher impacts and their landing scatter."""

from dataclasses import dataclass
import math

from . import effects
from . import radar


class LauncherAmmo:
    """Selectable launcher ammunition with its own range bands and payload."""

    def __init__(self, name, rangeBands, payload="explosive", charges=None,
                 damageModifier=0, blastRadius=0, blastSize=0,
                 effectRadius=0, effectTurns=2, scoutVision=0, igniteChance=0):
        self.name = name
        self.rangeBands = rangeBands
        self.payload = payload
        self.maxCharges = charges
        self.charges = charges
        self.damageModifier = damageModifier
        self.blastRadius = blastRadius
        self.blastSize = blastSize
        self.effectRadius = effectRadius
        self.effectTurns = effectTurns
        self.scoutVision = scoutVision
        self.igniteChance = igniteChance

        if payload not in {"explosive", "smoke", "incendiary", "scout"}:
            raise ValueError("Launcher ammunition payload must be explosive, smoke, incendiary, or scout.")
        if payload == "scout" and scoutVision <= 0:
            raise ValueError("Scout ammunition needs positive scoutVision.")
        if not 0 <= igniteChance <= 1:
            raise ValueError("Launcher ammunition igniteChance must be between 0 and 1.")
        if set(rangeBands) != {"close", "medium", "far"}:
            raise ValueError("Launcher ammunition needs close, medium, and far bands.")
        for band, values in rangeBands.items():
            if len(values) not in (3, 4):
                raise ValueError(f"Ammo {band} band needs 3 or 4 values.")
            if values[0] <= 0 or values[1] < 0 or values[2] < 0:
                raise ValueError(f"Ammo {band} needs positive range and nonnegative scatter/turns.")

    def profile(self, distance, range_bonus=0):
        """Return the first band able to reach this target distance."""
        range_bonus = max(0, int(range_bonus))
        for name in ("close", "medium", "far"):
            values = self.rangeBands[name]
            max_range, inaccuracy, turns = values[:3]
            falloff = values[3] if len(values) == 4 else 0
            if distance <= max_range + range_bonus:
                return {
                    "name": name,
                    "max_range": max_range + range_bonus,
                    "range_bonus": range_bonus,
                    "inaccuracy": inaccuracy,
                    "turns": turns,
                    "damage_falloff": falloff,
                }
        return None


@dataclass
class ScheduledImpact:
    """One shell in flight, due on a match round rather than a squad handoff."""

    position: list[int]
    turns_remaining: int
    radius: int
    size: int
    damage: int
    weapon_name: str
    payload: str
    effect_radius: int
    effect_turns: int
    scout_vision: int
    owner_team: object
    ignite_chance: float
    sound_range: int
    impact_round: int
    source_entity: object = None


def auto_lead_available(match_info, observer, target):
    """Require team sight or a fully identified radar track for auto lead."""
    return target is not None and (
        radar.team_has_visual_contact(observer, target)
        or radar.can_aim_at_contact(observer, match_info, target)
    )


def predict_launcher_lead(match_info, launcher, target, observer):
    """Project a valid contact forward by the launcher's actual flight time."""
    if not auto_lead_available(match_info, observer, target):
        return None

    detail = radar.contact_details(observer, match_info, target)
    visual_contact = radar.team_has_visual_contact(observer, target)
    position = list(target.pos) if visual_contact else list(detail["position"])
    if visual_contact:
        turn_start, speed = target.turnStartPos, target.speed
    else:
        memory = observer.team.radarContacts[target]
        turn_start, speed = memory["turn_start_pos"], memory["speed"]

    delta_x = position[0] - turn_start[0]
    delta_y = position[1] - turn_start[1]
    direction_x = (delta_x > 0) - (delta_x < 0)
    direction_y = (delta_y > 0) - (delta_y < 0)
    projected = list(position)
    for _ in range(3):
        profile = launcher.launcher_profile(
            math.dist(observer.pos, projected), match_info, observer,
        )
        if profile is None:
            return None
        updated = [
            position[0] + (direction_x * speed * profile["turns"]),
            position[1] + (direction_y * speed * profile["turns"]),
        ]
        if updated == projected:
            break
        projected = updated
    if not (1 <= projected[0] < match_info.mapWidth - 1 and 1 <= projected[1] < match_info.mapHeight - 1):
        return None
    return projected


def scatter_position(match_info, target, inherent_inaccuracy):
    """Return an in-bounds impact point scattered up to the weapon's tile error."""
    scatter = max(0, int(inherent_inaccuracy))
    if scatter == 0:
        return list(target)

    while True:
        offset_x = match_info.rng.randint(-scatter, scatter)
        offset_y = match_info.rng.randint(-scatter, scatter)
        if math.hypot(offset_x, offset_y) <= scatter:
            break

    # Keep a shell on playable terrain rather than allowing scatter to place it
    # beyond the generated world or on the impassable map border.
    x = min(max(1, target[0] + offset_x), match_info.mapWidth - 2)
    y = min(max(1, target[1] + offset_y), match_info.mapHeight - 2)
    return [x, y]


def schedule_impact(match_info, position, turns, radius, size, damage, weapon_name,
                    payload="explosive", effect_radius=0, effect_turns=2,
                    scout_vision=0, owner_team=None, ignite_chance=0, sound_range=0,
                    source_entity=None):
    """Store one delayed shell on the match until turn advancement resolves it."""
    impact = ScheduledImpact(
        list(position), turns, radius, size, damage, weapon_name,
        payload, effect_radius, effect_turns, scout_vision, owner_team, ignite_chance,
        sound_range, match_info.matchRound + turns, source_entity,
    )
    match_info.pendingImpacts.append(impact)
    return impact


def resolve_impact(match_info, impact):
    """Resolve one landed projectile without advancing any other shell."""
    print(f"{impact.weapon_name} impacts at {impact.position}!")
    if impact.payload == "explosive":
        match_info.explosion(
            impact.position, impact.radius, impact.size, impact.damage,
            soundRange=impact.sound_range,
            attacker=impact.source_entity or impact.owner_team,
        )
        if match_info.rng.random() < impact.ignite_chance:
            cell = match_info.map[impact.position[1]][impact.position[0]]
            effects.add_fire(cell, owner_team=impact.owner_team)
    elif impact.payload in {"smoke", "incendiary"}:
        for row in match_info.map:
            for cell in row:
                if math.dist(cell.pos, impact.position) <= impact.effect_radius:
                    if impact.payload == "smoke":
                        effects.add_smoke(cell, impact.effect_turns)
                    else:
                        effects.add_fire(cell, impact.effect_turns, owner_team=impact.owner_team)
    else:
        cell = match_info.map[impact.position[1]][impact.position[0]]
        effects.add_scout_flare(
            cell, impact.owner_team, impact.scout_vision, impact.effect_turns,
        )


def advance_impacts(match_info):
    """Resolve due rounds; extra squad handoffs cannot speed up flight time."""
    remaining = []
    for impact in match_info.pendingImpacts:
        impact.turns_remaining = max(0, impact.impact_round - match_info.matchRound)
        if impact.turns_remaining > 0:
            remaining.append(impact)
            continue

        resolve_impact(match_info, impact)
    match_info.pendingImpacts = remaining
