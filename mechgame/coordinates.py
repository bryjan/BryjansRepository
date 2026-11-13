"""Coordinate parsing and direction helpers shared by game systems.

The map is stored as ``map[y][x]``. Game positions remain ``[x, y]`` so they
read naturally in the HUD and player commands; keeping the convention here
prevents rectangular-map code from accidentally treating X as a row index.
"""

import math


def compass_bearing(point_a, point_b):
    # LICENSE: public domain
    """Return the compass bearing from one latitude/longitude point to another.

    This general helper predates the tactical map and is retained for callers
    that use geographic coordinates. Tactical direction labels use
    :func:`nesw_direction` below instead.
    """
    if not isinstance(point_a, tuple) or not isinstance(point_b, tuple):
        raise TypeError("Only tuples are supported as arguments")

    lat1 = math.radians(point_a[0])
    lat2 = math.radians(point_b[0])
    diff_long = math.radians(point_b[1] - point_a[1])

    x = math.sin(diff_long) * math.cos(lat2)
    y = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(diff_long)
    )
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def nesw_direction(point_a, point_b):
    """Convert one tactical-map position into a readable compass label.

    Map Y increases northward, matching the tactical display's coordinate axis.
    """
    dx = point_b[0] - point_a[0]
    dy = point_b[1] - point_a[1]
    horizontal = "East" if dx > 0 else "West" if dx < 0 else ""
    vertical = "North" if dy > 0 else "South" if dy < 0 else ""
    return f"{vertical} {horizontal}".strip() or "Stationary"


def get_coordinate_input(match_info, input_query):
    """Read one in-bounds ``x,y`` position, or return ``"x"`` to cancel.

    Validation deliberately checks X and Y against separate dimensions. This
    is essential for rectangular maps, where a valid wide-map X could exceed
    the map height.
    """
    while True:
        player_input = input(
            f"{input_query} (for example 'x,y', or 'x' to exit): "
        ).strip()
        if player_input.lower() == "x":
            return "x"

        try:
            x_text, y_text = player_input.split(",")
            x, y = int(x_text), int(y_text)
        except ValueError:
            print("Enter coordinates as two whole numbers separated by one comma.")
            continue

        if 0 <= x < match_info.mapWidth and 0 <= y < match_info.mapHeight:
            return [x, y]

        print(
            f"[{x}, {y}] is not in the map. "
            f"Use X from 0 to {match_info.mapWidth - 1} and "
            f"Y from 0 to {match_info.mapHeight - 1}."
        )
