"""ASCII Mech Game package and its public construction API."""

from .runner import Game
from .catalog import create_ammo, create_mech, create_module, create_part, list_catalog
from .campaign import MercenaryCampaign

__all__ = ["Game", "MercenaryCampaign", "create_ammo", "create_mech", "create_module", "create_part", "list_catalog"]
