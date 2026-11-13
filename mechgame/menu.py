"""Small entry menu for the playable terminal demo."""


MENU_SCENE = (
    "       ^       ^       ^       ^",
    "      /|\\     /|\\     /|\\     /|\\",
    "     /|||\\   /|||\\   /|||\\   /|||\\",
    "      |||     |||     |||     |||",
    "                 /\\",
    "                /##\\",
    "               | [] |",
    "               |____|",
    "                /  \\",
    "               /_/\\_\\",
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
            output_func("Move: q w e / a d / z x c")
            output_func("'f' fire  |  'r' radar  |  'rd' contacts  |  'ab' abilities")
            output_func("'sq' squad  |  'rep1' unread reports  |  'end' finish turn")
            output_func("Use '?' during a match for the full command reference.")
            continue
        output_func("Choose '1', '?', or 'q'.")
