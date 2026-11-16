"""Launch the pre-match menu and playable demo skirmish."""

from mechgame import Game
from mechgame.ui.menu import start_menu


def main():
    settings = start_menu()
    if settings is None:
        return
    Game(
        window_width=settings.tactical_width,
        window_height=settings.tactical_height,
        terrain_enabled=settings.terrain_enabled,
        map_preset=settings.map_preset,
    ).run()


if __name__ == "__main__":
    main()
