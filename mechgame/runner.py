"""Application orchestration for a command-line match."""

import random

from .match import MatchInfo

from .content import create_demo_teams


class Game:
    """Owns match creation and the interactive loop."""

    def __init__(
        self, map_size=100, window_size=None, rng=None, map_width=None,
        map_height=None, window_width=None, window_height=None,
    ):
        if window_size is None:
            # The renderer imports game models, so resolve its display minimum
            # lazily instead of creating an import cycle during package setup.
            from .ui.tactical import MIN_TACTICAL_HEIGHT
            window_size = MIN_TACTICAL_HEIGHT
        self.map_width = map_size if map_width is None else map_width
        self.map_height = map_size if map_height is None else map_height
        # ``window_size`` remains the legacy square-view shorthand. The menu
        # can provide independent dimensions without changing test callers.
        self.window_size = window_size
        self.window_width = window_size if window_width is None else window_width
        self.window_height = window_size if window_height is None else window_height
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
        match.mapInit()
        # Spawn points are kept away from the impassable map border, but their
        # margin scales down safely for compact custom maps.
        xMargin = min(40, max(2, self.map_width // 4))
        yMargin = min(40, max(2, self.map_height // 4))
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
        while not match.matchOver:
            match.pov.getVisuals(match)
            tactical.printPOV(match, *match.pov.pos)
            receive_input(match)
            self.advance_turn_if_requested(match)
        print(match.resultMessage)

    @staticmethod
    def advance_turn_if_requested(match):
        """Advance only after an explicit ``end`` command.

        Movement and firing may set ``advTurn`` for their own rules, but they
        do not transfer control away from the active mech.
        """
        if match.turnEnded:
            match.nextSquadTurn()
