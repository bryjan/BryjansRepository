"""Top-level command dispatch for an active tactical match."""

from .firing import fire, gunMenu
from .navigation import abilityMenu, lookAt, mapView, radarToggle, statusPanel
from .shared import read_nonempty
from .squad import helpCommand, optionsMenu, reportMenu, squadMenu, unreadReportMenu


def receive_input(matchInfo):
    """Read one player command and dispatch it to the relevant game action."""
    player_input = read_nonempty("Input: ").lower()

    match player_input:
        case "quit":
            return matchInfo.request_quit()
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
        case "auto":
            from .orders import automatic_travel
            return automatic_travel(matchInfo)
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
        case "eject":
            return matchInfo.pov.eject(matchInfo)
        case "flee":
            # At the map edge this preserves the active mech immediately.
            # Elsewhere it is an explicit squad withdrawal order that begins
            # the squad's double-time exit movement immediately.
            if (
                matchInfo.pov.pos[0] in (0, matchInfo.mapWidth - 1)
                or matchInfo.pov.pos[1] in (0, matchInfo.mapHeight - 1)
            ):
                return matchInfo.pov.flee(matchInfo)
            matchInfo.pov.squad.orderFlee()
            from ..ai import execute_squad_flee
            execute_squad_flee(matchInfo, matchInfo.pov.squad)
            matchInfo.turnEnded = True
            print("Squad ordered to flee toward the nearest border exit.")
            return True
        case "end":
            # This is the sole command that hands control to the next squad.
            matchInfo.turnEnded = True
        case "look" | "l":
            return lookAt(matchInfo)
        case "m":
            return mapView(matchInfo)
        case "fire":
            return gunMenu(matchInfo)
        case "f":
            return fire(matchInfo)
        case _:
            print("Input not recognized. Try again.")
