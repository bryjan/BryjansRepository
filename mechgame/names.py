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

# Familiar skirmish pilots may also appear in a Mercenary Mode roster. These
# are complete preset names, so they do not need to follow first/last format.
PRESET_PILOT_NAMES = (
    "B", "MagikP", "Xactly", "115um6uy15", "Chiki", "Blastra", "UncLord", "Sybis", "Boly"
)

# Nicknames are informal pilot identities. Callsigns remain deliberately
# player-assigned; these are used when creating a new campaign roster.
NICKNAMES = (
    "Anchor", "Reaper", "Bolt", "Pigsty", "Thunder", "Zues", "Grit", "Haze",
    "Ivy", "Jinx", "Archer", "Fiend", "Ace", "Nix", "Omen", "Patch",
    "Quill", "Rook", "Sable", "Thorn", "Vale", "Wisp", "Yarrow", "Zinc",
)


def generate_random_name(rng, used_names=()):
    """Return an unused legal pilot name using the supplied RNG.

    Keeping the random generator as an argument lets campaign creation remain
    reproducible when the game is started with a seed.
    """
    used = set(used_names)
    generated_names = [
        f"{first} {last}"
        for first in FIRST_NAMES
        for last in LAST_NAMES
    ]
    candidates = [name for name in (*generated_names, *PRESET_PILOT_NAMES) if name not in used]
    if not candidates:
        raise ValueError("No unique pilot names remain.")
    return rng.choice(candidates)


def generate_pilot_name(rng, used_names=()):
    """Compatibility alias for the campaign's random legal-name generator."""
    return generate_random_name(rng, used_names)


def generate_random_nickname(rng, used_nicknames=()):
    """Return an unused generated nickname using the supplied RNG."""
    used = set(used_nicknames)
    candidates = [nickname for nickname in NICKNAMES if nickname not in used]
    if not candidates:
        raise ValueError("No unique generated nicknames remain.")
    return rng.choice(candidates)
