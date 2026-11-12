"""Application orchestration for a command-line match."""

import random

import inputs
import printHUD
import printView
from .match import MatchInfo

from .content import create_demo_teams


class Game:
    """Owns match creation and the interactive loop."""

    def __init__(self, map_size=100, window_size=19, rng=None):
        self.map_size = map_size
        self.window_size = window_size
        self.rng = rng or random.Random()

    def create_match(self):
        match = MatchInfo(self.map_size, self.window_size, create_demo_teams(), "")
        match.mapInit()
        spawn_margin = min(40, max(2, self.map_size // 4))
        for team in match.teamList:
            for squad in team.squadsList:
                if squad.playerControlled:
                    match.playerSquad = squad
                match.entities.extend(squad.mechList)
                squad.spawnSquad(
                    match.map,
                    [
                        self.rng.randint(spawn_margin, self.map_size - spawn_margin - 1),
                        self.rng.randint(spawn_margin, self.map_size - spawn_margin - 1),
                    ],
                )
        match.pov = match.playerSquad.mechList[0]
        return match

    def run(self):
        match = self.create_match()
        while True:
            for team in match.teamList:
                for squad in team.squadsList:
                    if not squad.playerControlled:
                        squad.roundRefresh(match)
            match.pov.squad.roundRefresh(match)
            while not match.advTurn:
                match.pov.getVisuals(match)
                printHUD.displayHUD(match)
                printView.printPOV(match, *match.pov.pos)
                inputs.receive_input(match)
