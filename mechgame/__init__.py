"""ASCII Mech Game package.

The package boundary keeps the command-line entry point, reusable game content,
and world generation separate from the domain objects retained in gameClasses.
"""

from .runner import Game
from .catalog import create_mech, create_module, create_part, list_catalog

__all__ = ["Game", "create_mech", "create_module", "create_part", "list_catalog"]
