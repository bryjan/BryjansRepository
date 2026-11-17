"""Launch the pre-match menu and playable demo skirmish."""

from mechgame import Game
from mechgame.ui.menu import start_menu


def main():
    while True:
        settings = start_menu()
        if settings is None:
            return
        match = Game(
            display_width=settings.display_width,
            display_height=settings.display_height,
            terrain_enabled=settings.terrain_enabled,
            map_preset=settings.map_preset,
        ).run()
        if not match.quitRequested:
            return


if __name__ == "__main__":
    main()
