"""Run the playable demo scenario."""

from mechgame import Game
from mechgame.menu import show_start_menu


def main():
    # Keep the menu separate from match setup: choosing Start creates a fresh,
    # randomly generated map and randomized spawn positions every time.
    if show_start_menu():
        Game().run()


if __name__ == "__main__":
    main()
