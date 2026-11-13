"""Playable scenarios built from the reusable mech catalog."""

from .catalog import create_mech
from .entities import Entity, Pilot
from .teams import Squad, Team


def create_demo_teams():
    """Create the playable sensor-and-artillery test match."""
    player_mechs = [
        Entity(create_mech("lancer.pathfinder"), Pilot("Kiki")),
        Entity(create_mech("lancer.mortar"), Pilot("Rook")),
        Entity(create_mech("lancer.mortar"), Pilot("Mira")),
    ]
    enemy_mechs = [
        Entity(create_mech("bastion"), Pilot("Bryan")),
        Entity(create_mech("kestrel"), Pilot("Wraith")),
        Entity(create_mech("lancer.type_a"), Pilot("Panda")),
    ]
    player = Team("Player Team", [Squad("Player Squad", player_mechs, "Combat", playerControlled=True)])
    enemies = Team("Enemy Team", [Squad("Enemy Squad", enemy_mechs, "Combat")])
    # The match begins with the player squad, so keep it first in turn order.
    # A complete round is then player turn, enemy turn, and back to player.
    return [player, enemies]
