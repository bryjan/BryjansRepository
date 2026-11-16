"""The small pre-match menu used to start a playable skirmish."""

from dataclasses import dataclass, field
import textwrap

from ..world import DEFAULT_TERRAIN_ENABLED, GENERATABLE_TERRAINS
from .tactical import MIN_TACTICAL_HEIGHT

MIN_TACTICAL_WIDTH = 5
MENU_MIN_INNER_WIDTH = 40


@dataclass
class DisplaySettings:
    """Display and map-generation choices collected before a match begins."""

    tactical_width: int = 19
    tactical_height: int = MIN_TACTICAL_HEIGHT
    terrain_enabled: dict = field(default_factory=lambda: dict(DEFAULT_TERRAIN_ENABLED))


def _frame_lines(lines, settings):
    """Build a fixed-size menu frame from the selected display dimensions."""
    # Tactical cells consume two terminal columns. Reusing that scale makes a
    # menu resized in Options visibly remain the same size on every page.
    width = max(MENU_MIN_INNER_WIDTH, settings.tactical_width * 2)
    content = []
    for line in lines:
        content.extend(textwrap.wrap(line, width=width) or [""])
    height = max(settings.tactical_height, len(content))
    divider = "+" + ("-" * (width + 2)) + "+"
    return [
        divider,
        *(f"| {line:<{width}} |" for line in content),
        *(f"| {'':<{width}} |" for _ in range(height - len(content))),
        divider,
    ]


def _frame(lines, settings):
    """Print a consistently sized pre-match menu frame."""
    for line in _frame_lines(lines, settings):
        print(line)


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
        ], settings)
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
        ], settings)
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
        _frame(lines, settings)
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
        ], settings)
        choice = input("Select: ").strip().lower()
        if choice == "s":
            return settings
        if choice == "o":
            options_menu(settings)
        elif choice in ("", "q", "x"):
            return None
        else:
            print("Choose 's', 'o', or 'q'.")
