"""Launch the pre-match menu and playable demo skirmish."""

from mechgame import Game
from mechgame.campaign import MercenaryCampaign
from mechgame.ui.menu import DisplaySettings, start_menu


def main():
    # These objects live for the application session, so returning from a
    # skirmish never silently replaces campaign pilots or contracts.
    settings = DisplaySettings()
    campaign = MercenaryCampaign.load_or_create()
    while True:
        selected_settings = start_menu(settings, campaign)
        if selected_settings is None:
            return
        match = Game(
            display_width=selected_settings.display_width,
            display_height=selected_settings.display_height,
            terrain_enabled=selected_settings.terrain_enabled,
            map_preset=selected_settings.map_preset,
            **({"scenario": selected_settings.scenario} if selected_settings.scenario != "skirmish" else {}),
        ).run()
        # Finished battles display their after-action report, then return here
        # so both ordinary and debug matches can be relaunched immediately.


if __name__ == "__main__":
    main()
