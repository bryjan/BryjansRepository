"""Playable scenarios built from the reusable mech catalog."""

from .catalog import create_mech
from .entities import Entity, Pilot
from .teams import Squad, Team


def create_demo_teams():
    """Create a playable sensor-Lancer test match."""
    player_mechs = [
        Entity(create_mech("lancer.pathfinder"), Pilot("Kiki")),
        Entity(create_mech("bastion"), Pilot("Bryan")),
    ]
    enemy_mechs = [
        Entity(create_mech("kestrel"), Pilot("Wraith")),
        Entity(create_mech("kestrel"), Pilot("Ghost")),
    ]
    player = Team("Player Team", [Squad("Player Squad", player_mechs, "Combat", playerControlled=True)])
    enemies = Team("Enemy Team", [Squad("Enemy Squad", enemy_mechs, "Combat")])
    return [enemies, player]
