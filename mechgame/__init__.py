"""ASCII Mech Game package.

The package boundary keeps the command-line entry point, reusable game content,
and world generation separate from the domain objects retained in gameClasses.
"""

from .runner import Game

__all__ = ["Game"]
