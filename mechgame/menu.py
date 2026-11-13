"""Small entry menu for the playable terminal demo."""


MENU_SCENE = (
    "             .-----------------.",
    "          .-'  .-----------.    '-.",
    "         /    /   _     _   \\     \\",
    "        |    |   | |___| |   |     |",
    "        |    |   |  ___  |   |     |",
    "        |    |   |_|   |_|   |     |",
    "         \\    \\_____________/    /",
    "          '._       | |       _.'",
    "             '------|_|------'",
)


MENU_HELP = (
    "DEMO ROSTER AND TACTICAL BRIEFING",
    "Player team:",
    "  B - Sensor Lancer: Scout Rifle; active radar and superior vision, but lighter armor.",
    "  MagikP, Xactly, 115um6uy15 - Standard Lancers: ChainGun + Plasma Lance; flexible, but must close to 1.5 tiles for anti-armor strikes.",
    "  Chiki - Mortar Lancer: HE x10, Smoke x5, Scout Flare x4, Incendiary x1; indirect support, but weak at close range.",
    "Enemy team:",
    "  Blastra, Sybis - Bastions: Heavy Melting Beam + Sustained ChainGun; durable and able to repair, but slow with no active radar.",
    "  UncLord - Kestrel: Energy Beam; long-range sensors and burst reserve, but leg damage sharply cuts mobility.",
    "",
    "MOVEMENT AND DESTRUCTION",
    "Each move costs 1 AP, 1 MP, and the destination tile's energy cost.",
    "Road 0 | plains 1 | desert: Lancer 3 / size-3 2 | forest: Lancer 2 / size-3 4 | suburbs: Lancer 1 / size-3 5.",
    "Occupied, impassable, and off-map tiles cannot be entered. Energy regenerates at the start of a mech's turn.",
    "A cockpit hit injures the pilot; a destroyed cockpit removes that mech from its squad and the match.",
    "Other damaged limbs and modules reduce capability without immediately destroying the mech.",
    "",
    "Press 'Enter' to return to the menu.",
)


def show_start_menu(input_func=input, output_func=print):
    """Show the demo entry screen and return whether to start a match.

    Maps and spawn points are deliberately created only after the player
    selects Start, preserving the normal random demo setup.
    """
    while True:
        output_func("")
        for line in MENU_SCENE:
            output_func(line)
        output_func("")
        output_func("'Enter' or '1' Start random skirmish")
        output_func("'?' Quick controls")
        output_func("'q' Quit")

        choice = input_func("Menu: ").strip().lower()
        if choice in ("", "1", "start"):
            return True
        if choice in ("q", "quit", "x", "exit"):
            return False
        if choice in ("?", "help"):
            output_func("")
            for line in MENU_HELP:
                output_func(line)
            input_func("")
            continue
        output_func("Choose '1', '?', or 'q'.")
