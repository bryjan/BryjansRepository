"""Persistent terrain effects created by shells and advanced each match round."""

import random


class TerrainEffect:
    """Base behavior for a visible, temporary effect attached to one map cell."""

    name = "effect"
    symbol = "?"
    color = "white"
    visual_absorption = 0
    radar_absorption = 0

    def tick(self, match_info, cell):
        """Return ``True`` when the effect should remain for another round."""
        return False

    def on_enter(self, match_info, entity):
        """Apply an immediate consequence when a mech enters the cell."""

    def on_turn_start(self, match_info, entity):
        """Apply a consequence when a mech begins its own squad turn here."""


class SmokeEffect(TerrainEffect):
    """Dense smoke that disrupts sight strongly and radar slightly."""

    name = "smoke"
    symbol = "S"
    color = "light_grey"
    visual_absorption = 12
    radar_absorption = 2

    def __init__(self, turns=2):
        self.turns_remaining = turns

    def tick(self, match_info, cell):
        self.turns_remaining -= 1
        # Smoke normally lasts close to two rounds, but either round may disperse
        # it early as wind changes.
        return self.turns_remaining > 0 and random.random() >= 0.35


class FireEffect(TerrainEffect):
    """Burning terrain that harms mechs and reacts to the terrain beneath it."""

    name = "fire"
    symbol = "*"
    color = "red"

    def __init__(self, turns=3):
        self.turns_remaining = turns

    def _damage_entity(self, match_info, entity):
        if entity.destroyed:
            return
        limb = random.choice(entity.mechClass.limbList)
        limb.damage(match_info, 8, "fire")

    def on_enter(self, match_info, entity):
        self._damage_entity(match_info, entity)

    def on_turn_start(self, match_info, entity):
        self._damage_entity(match_info, entity)

    def tick(self, match_info, cell):
        terrain = cell.terrain
        if terrain.fireproof:
            # Fireproof ground can receive a burning payload, but it cannot
            # propagate it and goes out after one complete match round.
            return False

        if terrain.name == "plains":
            spread_chance, extinguish_chance = 0.05, 0.45
        elif terrain.name == "forest":
            spread_chance, extinguish_chance = 0.25, 0.10
        elif terrain.name == "suburbs":
            spread_chance, extinguish_chance = 0.20, 0.15
        else:
            spread_chance, extinguish_chance = 0.10, 0.25

        for neighbor in cell.nList:
            if not neighbor.terrain.fireproof and random.random() < spread_chance:
                add_fire(neighbor)

        self.turns_remaining -= 1
        return self.turns_remaining > 0 and random.random() >= extinguish_chance


class ScoutFlareEffect(TerrainEffect):
    """A team-owned optical flare that projects temporary terrain-aware vision."""

    name = "scout flare"
    symbol = "!"
    color = "yellow"

    def __init__(self, owner_team, vision_power, turns=1):
        self.owner_team = owner_team
        self.vision_power = vision_power
        self.turns_remaining = turns

    def tick(self, match_info, cell):
        # Retain the flare through the next round transition so a shell that
        # lands during the enemy turn still gives its owner one full view.
        if self.turns_remaining == 0:
            return False
        self.turns_remaining -= 1
        return True


def add_effect(cell, effect):
    """Add one effect unless that effect type is already present on the cell."""
    if any(type(existing) is type(effect) for existing in cell.effects):
        return
    cell.effects.append(effect)
    cell.refresh_effect_flags()


def add_smoke(cell, turns=2):
    add_effect(cell, SmokeEffect(turns))


def add_fire(cell, turns=3):
    add_effect(cell, FireEffect(turns))


def add_scout_flare(cell, owner_team, vision_power, turns=1):
    """Place a temporary visual source for the firing team at an impact cell."""
    if any(
        isinstance(effect, ScoutFlareEffect) and effect.owner_team is owner_team
        for effect in cell.effects
    ):
        return
    cell.effects.append(ScoutFlareEffect(owner_team, vision_power, turns))
    cell.refresh_effect_flags()


def apply_entry_effects(match_info, entity):
    """Trigger hazards immediately after a mech successfully changes cells."""
    cell = match_info.map[entity.pos[1]][entity.pos[0]]
    for effect in tuple(cell.effects):
        effect.on_enter(match_info, entity)


def apply_turn_start_effects(match_info, entity):
    """Trigger hazards once when a mech begins its own squad turn."""
    cell = match_info.map[entity.pos[1]][entity.pos[0]]
    for effect in tuple(cell.effects):
        effect.on_turn_start(match_info, entity)


def scout_visible_cells(match_info, team):
    """Project every active friendly scout flare through terrain absorption."""
    visible = []
    for row in match_info.map:
        for cell in row:
            for effect in cell.effects:
                if isinstance(effect, ScoutFlareEffect) and effect.owner_team is team:
                    visible.extend(_project_flare_vision(cell, effect.vision_power))
    return list(dict.fromkeys(visible))


def _project_flare_vision(starting_cell, vision_power):
    """Flood optical vision from a flare without resetting ordinary mech sight."""
    best_power = {tuple(starting_cell.pos): vision_power}
    frontier = [starting_cell]
    visible = []
    while frontier:
        cell = frontier.pop(0)
        power = best_power[tuple(cell.pos)]
        cell.canSee = True
        visible.append(cell)
        for neighbor in cell.nList:
            next_power = power - neighbor.visualAbsorption - 1
            key = tuple(neighbor.pos)
            if next_power <= 0 or next_power <= best_power.get(key, -1):
                continue
            best_power[key] = next_power
            frontier.append(neighbor)
    return visible


def advance_effects(match_info):
    """Advance terrain effects once at the beginning of each full match round."""
    # Snapshot first so fire that spreads this round begins ticking next round
    # instead of cascading through the entire map in one update.
    initial_effects = [
        (cell, list(cell.effects))
        for row in match_info.map
        for cell in row
    ]
    for cell, starting_effects in initial_effects:
        retained = [
            effect for effect in starting_effects if effect.tick(match_info, cell)
        ]
        newly_added = [effect for effect in cell.effects if effect not in starting_effects]
        cell.effects[:] = [*retained, *newly_added]
        cell.refresh_effect_flags()
