"""Compatibility names for older scripts.

Coordinate helpers now live in :mod:`mechgame.coordinates` with the active
game code. These camel-case aliases keep legacy imports working unchanged.
"""

from mechgame.coordinates import compass_bearing, get_coordinate_input, nesw_direction


def neswDirection(pointA, pointB):
    """Compatibility alias for :func:`mechgame.coordinates.nesw_direction`."""
    return nesw_direction(pointA, pointB)


def getCoordinateInput(matchInfo, inputQuery):
    """Compatibility alias for :func:`mechgame.coordinates.get_coordinate_input`."""
    return get_coordinate_input(matchInfo, inputQuery)
