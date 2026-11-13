"""Small entry menu for the playable terminal demo."""

import textwrap


# Leave generous room beside the frame for narrow terminal windows and the
# input prompt, preventing the closing border from wrapping.
FRAME_WIDTH = 60
CONTENT_WIDTH = FRAME_WIDTH - 2

# A compact standard-style banner, kept below the frame width so every letter
# remains recognizable in ordinary Windows console fonts.
MENU_SCENE = (
    " __  __ ___ ___ _  _       ___   _   __  __ ___",
    "|  \\/  | __/ __| || |-----| __| /_\\ |  \\/  | __|",
    "| |\\/| | _| (__| __ |     | _| / _ \\| |\\/| | _|",
    "|_|  |_|___\\___|_||_|     |___/_/ \\_\\_|  |_|___|",
    "",
    " ___  ___ __  __  ___",
    "|   \\| __|  \\/  |/ _ \\",
    "| |) | _|| |\\/| | (_) |",
    "|___/|___|_|  |_|\\___/",
)


MENU_HELP = (
    ("DEMO ROSTER", "center"),
    ("PLAYER TEAM", "center"),
    "B | Sensor Lancer | Scout Rifle",
    "    Strong active radar and superior vision; lighter armor and only one direct-fire weapon.",
    "MagikP, Xactly, 115um6uy15 | Standard Lancers | ChainGun + Plasma Lance",
    "    Flexible generalists; must close to 1.5 tiles for their armor-piercing lance.",
    "Chiki | Mortar Lancer | HE x10, Smoke x5, Scout Flare x4, Incendiary x1",
    "    Indirect support and terrain control; vulnerable at close range.",
    "",
    ("ENEMY TEAM", "center"),
    "Blastra, Sybis | Bastions | Heavy Melting Beam + Sustained ChainGun",
    "    Durable, able to repair, and dangerous in sustained combat; slow with no active radar.",
    "UncLord | Kestrel | Energy Beam",
    "    Long-range sensors and burst reserve; leg damage sharply cuts mobility.",
    "",
    ("MOVEMENT", "center"),
    "Every step spends 1 AP, 1 MP, and the energy cost of the destination tile.",
    "Road: 0 | Plains: 1 | Desert: Lancer 3 / Size-3 2",
    "Forest: Lancer 2 / Size-3 4 | Suburbs: Lancer 1 / Size-3 5",
    "Occupied, impassable, and off-map tiles cannot be entered. Energy regenerates at the start of a mech's turn.",
    "",
    ("DESTRUCTION", "center"),
    "A cockpit hit injures the pilot. A destroyed cockpit removes that mech from its squad and the match.",
    "Other damaged limbs and modules reduce capability without immediately destroying the mech.",
    "",
    ("Press 'Enter' to return to the menu.", "center"),
)


def _print_frame(lines, output_func):
    """Print consistently bordered menu text with readable wrapped paragraphs."""
    border = "+" + ("-" * FRAME_WIDTH) + "+"
    output_func(border)
    for entry in lines:
        text, alignment = entry if isinstance(entry, tuple) else (entry, "left")
        wrapped = textwrap.wrap(text, width=CONTENT_WIDTH) or [""]
        for line in wrapped:
            content = line.center(CONTENT_WIDTH) if alignment == "center" else line
            output_func(f"| {content:<{CONTENT_WIDTH}} |")
    output_func(border)


def show_start_menu(input_func=input, output_func=print):
    """Show the demo entry screen and return whether to start a match.

    Maps and spawn points are deliberately created only after the player
    selects Start, preserving the normal random demo setup.
    """
    while True:
        output_func("")
        _print_frame(
            [*( (line, "center") for line in MENU_SCENE), "", ("'Enter' or '1' Start random skirmish", "center"), ("'?' Quick controls", "center"), ("'q' Quit", "center")],
            output_func,
        )

        choice = input_func("Menu: ").strip().lower()
        if choice in ("", "1", "start"):
            return True
        if choice in ("q", "quit", "x", "exit"):
            return False
        if choice in ("?", "help"):
            output_func("")
            _print_frame(MENU_HELP, output_func)
            input_func("")
            continue
        output_func("Choose '1', '?', or 'q'.")
