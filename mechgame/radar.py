"""Shared radar-detection rules for mech targets."""

# A fixed baseline makes a larger signature easier, rather than harder, to
# find.  The larger scale leaves room for low-observable units to matter.
RADAR_DETECTION_BASE = 400

# Radar travels one map cell at a time.  Open ground has an absorption of one,
# so its total loss is two power per tile: one for distance and one for terrain.
RADAR_DISTANCE_LOSS = 1


def entity_detection_threshold(radar_signature):
    """Return the radar power required to obtain a contact on an entity.

    A high radar signature reflects more energy and therefore lowers the power
    required for detection. Terrain keeps its separate radar-return values.
    """
    return max(1, RADAR_DETECTION_BASE - radar_signature)


def radar_step_loss(terrain_absorption):
    """Return the power lost while radar crosses one terrain cell."""
    return RADAR_DISTANCE_LOSS + int(terrain_absorption)
