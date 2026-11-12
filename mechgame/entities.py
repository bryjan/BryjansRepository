"""Mech instances and their pilots.

The implementations remain in ``legacy_models`` during the staged extraction;
new callers should import from this focused module.
"""

from .legacy_models import Entity, Pilot

__all__ = ["Entity", "Pilot"]
