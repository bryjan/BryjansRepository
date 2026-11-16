"""The small pre-match menu used to start a playable skirmish."""

from dataclasses import dataclass

from .tactical import MIN_TACTICAL_HEIGHT

MIN_TACTICAL_WIDTH = 5


@dataclass
class DisplaySettings:
    """Persistent display choices collected before a new match begins."""

    tactical_width: int = 19
    tactical_height: int = MIN_TACTICAL_HEIGHT


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
    """Change the same tactical width and height available during a match."""
    while True:
        _frame([
            "DISPLAY OPTIONS",
            f"'w' Tactical width:  {settings.tactical_width}",
            f"'h' Tactical height: {settings.tactical_height}",
            "'x' Back",
        ])
        choice = input("Options: ").strip().lower()
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
