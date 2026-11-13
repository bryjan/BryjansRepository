"""Delayed launcher impacts and their landing scatter."""

from dataclasses import dataclass
import math
import random

from . import effects


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
            if values[0] <= 0 or values[1] < 0 or values[2] < 1:
                raise ValueError(f"Ammo {band} needs positive range/turns and nonnegative scatter.")

    def profile(self, distance):
        """Return the first band able to reach this target distance."""
        for name in ("close", "medium", "far"):
            values = self.rangeBands[name]
            max_range, inaccuracy, turns = values[:3]
            falloff = values[3] if len(values) == 4 else 0
            if distance <= max_range:
                return {
                    "name": name,
                    "max_range": max_range,
                    "inaccuracy": inaccuracy,
                    "turns": turns,
                    "damage_falloff": falloff,
                }
        return None


@dataclass
class ScheduledImpact:
    """One shell already fired and waiting to resolve on a future squad turn."""

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


def scatter_position(match_info, target, inherent_inaccuracy):
    """Return an in-bounds impact point scattered up to the weapon's tile error."""
    scatter = max(0, int(inherent_inaccuracy))
    if scatter == 0:
        return list(target)

    while True:
        offset_x = random.randint(-scatter, scatter)
        offset_y = random.randint(-scatter, scatter)
        if math.hypot(offset_x, offset_y) <= scatter:
            break

    # Keep a shell on playable terrain rather than allowing scatter to place it
    # beyond the generated world or on the impassable map border.
    x = min(max(1, target[0] + offset_x), match_info.mapWidth - 2)
    y = min(max(1, target[1] + offset_y), match_info.mapHeight - 2)
    return [x, y]


def schedule_impact(match_info, position, turns, radius, size, damage, weapon_name,
                    payload="explosive", effect_radius=0, effect_turns=2,
                    scout_vision=0, owner_team=None, ignite_chance=0):
    """Store one delayed shell on the match until turn advancement resolves it."""
    impact = ScheduledImpact(
        list(position), turns, radius, size, damage, weapon_name,
        payload, effect_radius, effect_turns, scout_vision, owner_team, ignite_chance,
    )
    match_info.pendingImpacts.append(impact)
    return impact


def advance_impacts(match_info):
    """Advance all shells once per squad-turn handoff and resolve arrivals."""
    remaining = []
    for impact in match_info.pendingImpacts:
        impact.turns_remaining -= 1
        if impact.turns_remaining > 0:
            remaining.append(impact)
            continue

        print(f"{impact.weapon_name} impacts at {impact.position}!")
        if impact.payload == "explosive":
            match_info.explosion(impact.position, impact.radius, impact.size, impact.damage)
            if random.random() < impact.ignite_chance:
                cell = match_info.map[impact.position[1]][impact.position[0]]
                effects.add_fire(cell)
        elif impact.payload in {"smoke", "incendiary"}:
            for row in match_info.map:
                for cell in row:
                    if math.dist(cell.pos, impact.position) <= impact.effect_radius:
                        if impact.payload == "smoke":
                            effects.add_smoke(cell, impact.effect_turns)
                        else:
                            effects.add_fire(cell, impact.effect_turns)
        else:
            cell = match_info.map[impact.position[1]][impact.position[0]]
            effects.add_scout_flare(
                cell, impact.owner_team, impact.scout_vision, impact.effect_turns,
            )
    match_info.pendingImpacts = remaining
