"""Top-level command dispatch for an active tactical match."""

from .firing import fire, gunMenu
from .navigation import abilityMenu, lookAt, radarToggle, statusPanel
from .shared import read_nonempty
from .squad import helpCommand, optionsMenu, radarMenu, reportMenu, squadMenu, unreadReportMenu


def receive_input(matchInfo):
    """Read one player command and dispatch it to the relevant game action."""
    player_input = read_nonempty("Input: ").lower()

    match player_input:
        case "?":
            return helpCommand(matchInfo)
        case "rep":
            return reportMenu(matchInfo)
        case "rep1":
            return unreadReportMenu(matchInfo)
        case "st" | "status":
            return statusPanel(matchInfo)
        case "sq" | "squad":
            return squadMenu(matchInfo)
        case "o" | "options":
            return optionsMenu(matchInfo)
        case "n" | "next":
            return matchInfo.nextMechinTeam()
        case "q" | "w" | "e" | "a" | "s" | "d" | "z" | "c":
            return matchInfo.pov.moveMech(matchInfo, player_input)
        case "r" | "radar":
            return radarToggle(matchInfo)
        case "p":
            return matchInfo.pov.pulseRadar(matchInfo)
        case "ab" | "abilities":
            return abilityMenu(matchInfo)
        case "rd":
            return radarMenu(matchInfo)
        case "end":
            # This is the sole command that hands control to the next squad.
            matchInfo.turnEnded = True
        case "look" | "l":
            return lookAt(matchInfo)
        case "fire":
            return gunMenu(matchInfo)
        case "f":
            return fire(matchInfo)
        case _:
            print("Input not recognized. Try again.")
