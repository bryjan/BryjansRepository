"""Legacy compatibility imports for the pre-split combat module.

New code should import from ``entities``, ``mechs``, ``teams``, ``match``, or
``terrain`` according to the responsibility it needs. This module remains so
older scripts keep the original import paths without maintaining duplicate
implementations.
"""

from .entities import Entity, Pilot
from .match import MatchInfo
from .mechs import Cockpit, Helm, Hull, Legs, MechClass, MechPart, Module, WeaponLimb
from .teams import Squad, Team
from .terrain import Cell, TerrainType

__all__ = [
    "Cell", "Cockpit", "Entity", "Helm", "Hull", "Legs", "MatchInfo",
    "MechClass", "MechPart", "Module", "Pilot", "Squad", "Team",
    "TerrainType", "WeaponLimb",
]
