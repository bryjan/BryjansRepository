"""Reusable rectangular map-stamp geometry.

Stamps describe shape only.  Map generation decides which terrain each stamp
uses, where it can be placed, and which strategic features it records.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RectangleStamp:
    """A rectangle whose outer ring can be shared with an adjacent stamp."""

    width: int
    height: int

    def positions(self, origin):
        """Return every map position covered by this stamp."""
        origin_x, origin_y = origin
        return tuple(
            (x, y)
            for y in range(origin_y, origin_y + self.height)
            for x in range(origin_x, origin_x + self.width)
        )

    def boundary_positions(self, origin):
        """Return the outer ring, used for roads and shared block edges."""
        origin_x, origin_y = origin
        return tuple(
            (x, y)
            for y in range(origin_y, origin_y + self.height)
            for x in range(origin_x, origin_x + self.width)
            if (
                x in (origin_x, origin_x + self.width - 1)
                or y in (origin_y, origin_y + self.height - 1)
            )
        )


@dataclass(frozen=True)
class CityBlockStamp(RectangleStamp):
    """A square urban block with a road perimeter."""


@dataclass(frozen=True)
class MilitaryBaseStamp(RectangleStamp):
    """A small rectangular base compound with a road perimeter."""

    MIN_WIDTH = 3
    MAX_WIDTH = 10
    MIN_HEIGHT = 3
    MAX_HEIGHT = 10
    ROAD_CONNECTION_AREA = 13

    @classmethod
    def random(cls, rng):
        """Create one 3–10 tile rectangular base footprint."""
        return cls(
            rng.randint(cls.MIN_WIDTH, cls.MAX_WIDTH),
            rng.randint(cls.MIN_HEIGHT, cls.MAX_HEIGHT),
        )

    @property
    def area(self):
        """Return the number of tiles occupied by the compound."""
        return self.width * self.height
