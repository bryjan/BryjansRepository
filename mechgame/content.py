"""Playable scenarios built from the reusable mech catalog."""

from .catalog import create_mech
from .entities import Entity, Pilot
from .teams import Squad, Team


def create_lancer_class():
    """Compatibility alias for the standard Lancer catalog entry."""
    return create_mech("lancer.type_a")


def create_sensor_lancer_class():
    """Compatibility alias for the Pathfinder catalog entry."""
    return create_mech("lancer.pathfinder")


def create_kestrel_class():
    """Compatibility alias for the Kestrel catalog entry."""
    return create_mech("kestrel")


def create_demo_teams():
    """Create a playable sensor-Lancer test match."""
    player_mechs = [
        Entity(create_mech("lancer.pathfinder"), Pilot("Kiki")),
        Entity(create_mech("lancer.type_a"), Pilot("Bryan")),
    ]
    enemy_mechs = [
        Entity(create_mech("kestrel"), Pilot("Wraith")),
        Entity(create_mech("lancer.type_a"), Pilot("Ghost")),
    ]
    player = Team("Player Team", [Squad("Player Squad", player_mechs, "Combat", playerControlled=True)])
    enemies = Team("Enemy Team", [Squad("Enemy Squad", enemy_mechs, "Combat")])
    return [enemies, player]
