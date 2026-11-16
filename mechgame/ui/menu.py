"""The small pre-match menu used to start a playable skirmish."""

from dataclasses import dataclass, field

from ..world import DEFAULT_TERRAIN_ENABLED, GENERATABLE_TERRAINS
from .tactical import MIN_TACTICAL_HEIGHT

MIN_TACTICAL_WIDTH = 5


@dataclass
class DisplaySettings:
    """Display and map-generation choices collected before a match begins."""

    tactical_width: int = 19
    tactical_height: int = MIN_TACTICAL_HEIGHT
    terrain_enabled: dict = field(default_factory=lambda: dict(DEFAULT_TERRAIN_ENABLED))


def _frame(lines):
    """Print a consistently bordered menu sized to its longest row."""
    width = max(len(line) for line in lines)
    divider = "+" + ("-" * (width + 2)) + "+"
    print(divider)
    for line in lines:
        print(f"| {line:<{width}} |")
    print(divider)


def _read_odd_size(dimension, current, minimum):
    """Prompt for one usable centered-view dimension, or retain the old value."""
    while True:
        value = input(
            f"{dimension} (odd whole number, at least {minimum}; 'x' to cancel): "
        ).strip().lower()
        if value in ("", "x"):
            return current
        if value.isdigit() and int(value) >= minimum and int(value) % 2 == 1:
            return int(value)
        print(f"Enter an odd whole number of at least {minimum}, or 'x' to cancel.")


def options_menu(settings):
    """Open display or optional-terrain settings before a match begins."""
    while True:
        _frame([
            "OPTIONS",
            "'d' Display size",
            "'m' Map tile generation",
            "'x' Back",
        ])
        choice = input("Options: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "d":
            display_options_menu(settings)
        elif choice == "m":
            terrain_options_menu(settings)
        else:
            print("Choose 'd', 'm', or 'x'.")


def display_options_menu(settings):
    """Change the same tactical width and height available during a match."""
    while True:
        _frame([
            "DISPLAY SIZE",
            f"'w' Tactical width:  {settings.tactical_width}",
            f"'h' Tactical height: {settings.tactical_height}",
            "'x' Back",
        ])
        choice = input("Display: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "w":
            settings.tactical_width = _read_odd_size(
                "Tactical width", settings.tactical_width, MIN_TACTICAL_WIDTH
            )
        elif choice == "h":
            settings.tactical_height = _read_odd_size(
                "Tactical height", settings.tactical_height, MIN_TACTICAL_HEIGHT
            )
        else:
            print("Choose 'w', 'h', or 'x'.")


def terrain_options_menu(settings):
    """Toggle optional terrain generators without affecting structural tiles."""
    while True:
        lines = ["MAP TILE GENERATION"]
        for index, terrain in enumerate(GENERATABLE_TERRAINS, start=1):
            status = "ON" if settings.terrain_enabled[terrain] else "OFF"
            lines.append(f"'{index}' {terrain.title()}: {status}")
        lines.extend(["", "Plains and borders are always generated.", "'x' Back"])
        _frame(lines)
        choice = input("Map tiles: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(GENERATABLE_TERRAINS):
            terrain = GENERATABLE_TERRAINS[int(choice) - 1]
            settings.terrain_enabled[terrain] = not settings.terrain_enabled[terrain]
        else:
            print(f"Choose a number from 1 to {len(GENERATABLE_TERRAINS)}, or 'x'.")


def start_menu(settings=None):
    """Return chosen settings when Skirmish starts, or ``None`` when quitting."""
    settings = settings or DisplaySettings()
    while True:
        _frame([
            "ASCII MECH GAME",
            "",
            "'s' Skirmish",
            "'o' Options",
            "'q' Quit",
        ])
        choice = input("Select: ").strip().lower()
        if choice == "s":
            return settings
        if choice == "o":
            options_menu(settings)
        elif choice in ("", "q", "x"):
            return None
        else:
            print("Choose 's', 'o', or 'q'.")
