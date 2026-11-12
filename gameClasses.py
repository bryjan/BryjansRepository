"""Compatibility imports for the original top-level module path."""

from mechgame.entities import Entity, Pilot
from mechgame.match import MatchInfo
from mechgame.mechs import Cockpit, Helm, Hull, Legs, MechClass, MechPart, Module, WeaponLimb
from mechgame.teams import Squad, Team
from mechgame.terrain import Cell, TerrainType

__all__ = [
    "Cell", "Cockpit", "Entity", "Helm", "Hull", "Legs", "MatchInfo",
    "MechClass", "MechPart", "Module", "Pilot", "Squad", "Team",
    "TerrainType", "WeaponLimb",
]
