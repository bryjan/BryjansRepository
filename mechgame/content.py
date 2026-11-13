"""Playable scenarios built from the reusable mech catalog."""

from .catalog import create_mech
from .entities import Entity, Pilot
from .teams import Squad, Team


def create_demo_teams():
    """Create the playable sensor-and-artillery test match."""
    player_mechs = [
        Entity(create_mech("lancer.pathfinder"), Pilot("B")),
        Entity(create_mech("lancer.type_a"), Pilot("MagikP")),
        Entity(create_mech("lancer.type_a"), Pilot("Xactly")),
        Entity(create_mech("lancer.mortar"), Pilot("Chiki")),
    ]
    enemy_mechs = [
        Entity(create_mech("bastion"), Pilot("Blastra")),
        Entity(create_mech("kestrel"), Pilot("UncLord")),
        Entity(create_mech("bastion"), Pilot("Sybis")),
    ]
    player = Team("Player Team", [Squad("Player Squad", player_mechs, "Combat", playerControlled=True)])
    enemies = Team("Enemy Team", [Squad("Enemy Squad", enemy_mechs, "Combat")])
    # The match begins with the player squad, so keep it first in turn order.
    # A complete round is then player turn, enemy turn, and back to player.
    return [player, enemies]
