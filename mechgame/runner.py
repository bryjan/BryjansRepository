"""Application orchestration for a command-line match."""

import random

from .match import MatchInfo

from .content import create_demo_teams


MIN_PLAYABLE_MAP_SIZE = 40


class Game:
    """Owns match creation and the interactive loop."""

    def __init__(
        self, map_size=100, window_size=None, rng=None, map_width=None,
        map_height=None, window_width=None, window_height=None, display_width=None,
        display_height=None, terrain_enabled=None,
        map_preset=None,
    ):
        if window_size is None:
            # Resolve the renderer's standard view lazily instead of creating
            # an import cycle during package setup.
            from .ui.tactical import DEFAULT_TACTICAL_SIZE
            window_size = DEFAULT_TACTICAL_SIZE
        self.map_width = map_size if map_width is None else map_width
        self.map_height = map_size if map_height is None else map_height
        if self.map_width < MIN_PLAYABLE_MAP_SIZE or self.map_height < MIN_PLAYABLE_MAP_SIZE:
            raise ValueError(
                f"Playable maps must be at least {MIN_PLAYABLE_MAP_SIZE}x{MIN_PLAYABLE_MAP_SIZE}."
            )
        # ``window_size`` remains the legacy square tactical-view shorthand.
        # Player-facing menus instead provide complete display dimensions.
        self.window_size = window_size
        if display_width is not None or display_height is not None:
            if display_width is None or display_height is None:
                raise ValueError("Provide both display_width and display_height.")
            from .ui.tactical import tactical_dimensions
            self.window_width, self.window_height = tactical_dimensions(display_width, display_height)
            self.display_width = display_width
            self.display_height = display_height
        else:
            self.window_width = window_size if window_width is None else window_width
            self.window_height = window_size if window_height is None else window_height
            from .ui.tactical import display_dimensions
            self.display_width, self.display_height = display_dimensions(
                self.window_width, self.window_height,
            )
        self.terrain_enabled = terrain_enabled
        self.map_preset = map_preset
        self.rng = rng if rng is not None else random.Random()

    def create_match(self):
        match = MatchInfo(
            self.map_width,
            self.window_height,
            create_demo_teams(),
            "",
            self.map_height,
            rng=self.rng,
        )
        match.windowWidth = self.window_width
        match.windowHeight = self.window_height
        match.displayWidth = self.display_width
        match.displayHeight = self.display_height
        match.mapInit(
            terrain_enabled=self.terrain_enabled,
            map_preset=self.map_preset,
        )
        # Playable maps are at least 40x40, so a quarter-map spawn margin
        # keeps opposing squads apart without compact-map special cases.
        xMargin = self.map_width // 4
        yMargin = self.map_height // 4
        for team in match.teamList:
            for squad in team.squadsList:
                if squad.playerControlled:
                    match.playerSquad = squad
                # Match-wide queries (vision, radar, targeting) operate on
                # this flat list; squads retain turn order and ownership.
                match.entities.extend(squad.mechList)
                squad.spawnSquad(
                    match.map,
                    [
                        self.rng.randint(xMargin, self.map_width - xMargin - 1),
                        self.rng.randint(yMargin, self.map_height - yMargin - 1),
                    ],
                    rng=self.rng,
                )
        match.pov = match.playerSquad.mechList[0]
        return match

    def run(self):
        # Terminal interaction belongs at the application boundary. Keeping
        # these imports here lets domain objects load without UI dependencies.
        from .ui import tactical
        from .commands import receive_input

        match = self.create_match()
        match.pov.squad.roundRefresh(match)
        while not match.matchOver and not match.quitRequested:
            match.pov.getVisuals(match)
            tactical.printPOV(match, *match.pov.pos)
            receive_input(match)
            if not match.quitRequested:
                self.advance_turn_if_requested(match)
        if match.matchOver:
            print(match.resultMessage)
        return match

    @staticmethod
    def advance_turn_if_requested(match):
        """Advance only after an explicit ``end`` command.

        Movement and firing may set ``advTurn`` for their own rules, but they
        do not transfer control away from the active mech.
        """
        if match.turnEnded:
            match.nextSquadTurn()
