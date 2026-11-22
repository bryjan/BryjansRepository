"""Small deterministic-friendly name helpers for persistent campaign crews."""

FIRST_NAMES = (
    "Avery", "Briar", "Cinder", "Dara", "Ember", "Fenn", "Gale", "Harper",
    "Indra", "Jules", "Kei", "Lark", "Mara", "Niko", "Orin", "Pax",
    "Quinn", "Rook", "Sable", "Tarin", "Uma", "Vale", "Wren", "Yara",
)

CALLSIGNS = (
    "Arrow", "Bishop", "Comet", "Drift", "Ember", "Fable", "Ghost", "Hawk",
    "Iris", "Jolt", "Kestrel", "Lumen", "Mako", "Nova", "Onyx", "Piper",
    "Quarry", "Raven", "Sparrow", "Thorn", "Viper", "Willow", "Yonder", "Zephyr",
)


def generate_pilot_name(rng, used_names=()):
    """Return an unused callsign-style pilot name using the supplied RNG.

    Keeping the random generator as an argument lets campaign creation remain
    reproducible when the game is started with a seed.
    """
    used = set(used_names)
    candidates = [
        f"{first} {callsign}"
        for first in FIRST_NAMES
        for callsign in CALLSIGNS
        if f"{first} {callsign}" not in used
    ]
    if not candidates:
        raise ValueError("No unique pilot names remain.")
    return rng.choice(candidates)
