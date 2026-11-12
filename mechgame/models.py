"""Compatibility exports for the original single-module model API.

New code should import from the focused modules: ``match``, ``terrain``,
``entities``, ``mechs``, and ``teams``.
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
