"""Shared radar-detection rules for mech targets."""

# Existing hull signatures cluster around 250. Keeping the scale while using a
# fixed baseline makes a larger signature easier, rather than harder, to find.
RADAR_DETECTION_BASE = 300


def entity_detection_threshold(radar_signature):
    """Return the radar power required to obtain a contact on an entity.

    A high radar signature reflects more energy and therefore lowers the power
    required for detection. Terrain keeps its separate radar-return values.
    """
    return max(1, RADAR_DETECTION_BASE - radar_signature)
