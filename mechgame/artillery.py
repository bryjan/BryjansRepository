"""Delayed launcher impacts and their landing scatter."""

from dataclasses import dataclass
import math
import random


@dataclass
class ScheduledImpact:
    """One shell already fired and waiting to resolve on a future squad turn."""

    position: list[int]
    turns_remaining: int
    radius: int
    size: int
    damage: int
    weapon_name: str


def turns_to_impact(distance, turns_per_tile):
    """Convert launcher travel rate into future squad-turn handoffs.

    Launcher shells always resolve later, even at close range. A rate of 0.03
    therefore produces a three-turn arrival time at 100 tiles.
    """
    return max(1, math.ceil(distance * turns_per_tile))


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


def schedule_impact(match_info, position, turns, radius, size, damage, weapon_name):
    """Store one delayed shell on the match until turn advancement resolves it."""
    impact = ScheduledImpact(list(position), turns, radius, size, damage, weapon_name)
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
        match_info.explosion(impact.position, impact.radius, impact.size, impact.damage)
    match_info.pendingImpacts = remaining
