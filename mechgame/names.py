"""Deterministic-friendly naming helpers for persistent campaign crews."""

FIRST_NAMES = (
    "Avery", "Briar", "Cinder", "Dara", "Ember", "Fenn", "Gale", "Harper",
    "Indra", "Jules", "Kei", "Lark", "Mara", "Niko", "Orin", "Pax",
    "Quinn", "Rook", "Sable", "Tarin", "Uma", "Vale", "Wren", "Yara",
)

LAST_NAMES = (
    "Archer", "Bennett", "Calloway", "Dawson", "Ellis", "Farrow", "Graves", "Hale",
    "Ibarra", "Jensen", "Kade", "Linden", "Mercer", "Navarro", "Ortega", "Parker",
    "Quade", "Rowan", "Sato", "Tanner", "Underwood", "Voss", "Wilder", "York",
)


def generate_random_name(rng, used_names=()):
    """Return an unused legal pilot name using the supplied RNG.

    Keeping the random generator as an argument lets campaign creation remain
    reproducible when the game is started with a seed.
    """
    used = set(used_names)
    candidates = [
        f"{first} {last}"
        for first in FIRST_NAMES
        for last in LAST_NAMES
        if f"{first} {last}" not in used
    ]
    if not candidates:
        raise ValueError("No unique pilot names remain.")
    return rng.choice(candidates)


def generate_pilot_name(rng, used_names=()):
    """Compatibility alias for the campaign's random legal-name generator."""
    return generate_random_name(rng, used_names)
