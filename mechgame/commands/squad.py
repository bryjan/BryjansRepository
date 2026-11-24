"""Commands for squad management, reports, and display options."""

from ..ui import tactical as pv

from .shared import read_nonempty


def _print_options_panel(matchInfo, command_text):
    """Render live display options inside the tactical command bar."""
    pv.printPOV(matchInfo, *matchInfo.pov.pos, command_text=command_text)


def squadMenu(matchInfo):
    """Show squad readiness and roster before player-facing squad controls."""
    squad = matchInfo.pov.squad
    entries = [*squad.statusReport().splitlines(), *squad.rosterReport().splitlines()]
    travel_state = "ON" if squad.autoTravelEnabled else "OFF"
    entries.extend(["", f"'v' Auto Travel: {travel_state}",
                    "Followers move after the squad leader; toggle with 'v'."])
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text=f"Squad: 'm' switch mech | 's' switch squad | 'a' AI/manual control | 'o' orders | 'v' Auto Travel ({travel_state}) | 'x' exit",
        right_panel=("SQUAD", entries),
    )
    choice = input("Squad: ").strip().lower()

    if choice in ("", "x"):
        return
    if choice == "m":
        return selectSquadMech(matchInfo, squad)
    if choice == "s":
        return selectControllableSquad(matchInfo)
    from .orders import control_menu, order_menu, automatic_travel
    if choice == "a":
        return control_menu(matchInfo)
    if choice == "o":
        return order_menu(matchInfo)
    if choice == "v":
        return automatic_travel(matchInfo)
    print("Choose 'm', 's', 'a', 'o', 'v', or 'x'.")


def optionsMenu(matchInfo):
    """Offer display preferences that do not alter match state."""
    option_prompt = (
        f"Options: 'w' display width ({matchInfo.displayWidth}) | "
        f"'h' display height ({matchInfo.displayHeight}) | 'x' exit"
    )
    _print_options_panel(matchInfo, option_prompt)
    choice = input("Options: ").strip().lower()
    if choice in ("", "x"):
        return
    if choice not in ("w", "h"):
        print("Choose 'w', 'h', or 'x'.")
        return

    dimension = "width" if choice == "w" else "height"
    while True:
        _print_options_panel(
            matchInfo,
            f"Options: enter display {dimension} | 'x' cancel",
        )
        size = input(
            f"Display {dimension} (whole number; 'x' to cancel): "
        ).strip().lower()
        if size == "x":
            return
        if size.isdigit():
            display_width = int(size) if choice == "w" else matchInfo.displayWidth
            display_height = int(size) if choice == "h" else matchInfo.displayHeight
            try:
                matchInfo.windowWidth, matchInfo.windowHeight = pv.tactical_dimensions(
                    display_width, display_height,
                )
            except ValueError as error:
                print(error)
                continue
            matchInfo.displayWidth = display_width
            matchInfo.displayHeight = display_height
            print(f"Display {dimension} set to {size}.")
            return
        print("Enter a whole number or 'x' to cancel.")


def selectSquadMech(matchInfo, squad):
    """Switch the point of view to a mech in the current squad."""
    entries = [
        f"'{index}' {mech.pilot.display_name} — {mech.mechClass.name} ({round(mech.mechClass.condition)}%)"
        for index, mech in enumerate(squad.mechList, start=1)
    ]
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Mech: enter a listed number | 'x' cancel",
        right_panel=("SWITCH MECH", entries),
    )
    selection = read_nonempty("Mech: ")
    if selection.lower() == "x":
        return
    if not selection.isdigit() or not 1 <= int(selection) <= len(squad.mechList):
        print("Choose a listed mech number.")
        return
    matchInfo.pov = squad.mechList[int(selection) - 1]
    matchInfo.advTurn = False


def selectControllableSquad(matchInfo):
    """Switch to a non-empty squad explicitly marked as player controlled."""
    squads = [
        squad
        for team in matchInfo.teamList
        for squad in team.squadsList
        if squad.playerControlled and squad.mechList
    ]
    if not squads:
        print("No controllable squads are available.")
        return
    entries = [
        f"'{index}' {squad.name} — {len(squad.mechList)} mechs"
        for index, squad in enumerate(squads, start=1)
    ]
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Squad: enter a listed number | 'x' cancel",
        right_panel=("SWITCH SQUAD", entries),
    )
    selection = read_nonempty("Squad: ")
    if selection.lower() == "x":
        return
    if not selection.isdigit() or not 1 <= int(selection) <= len(squads):
        print("Choose a listed squad number.")
        return
    matchInfo.pov = squads[int(selection) - 1].mechList[0]
    matchInfo.playerSquad = matchInfo.pov.squad
    matchInfo.advTurn = False


def reportMenu(matchInfo):
    """Browse the squad report log inside the right tactical panel."""
    reports = matchInfo.pov.squad.reportLog
    page_size = max(1, matchInfo.windowHeight - 2)
    page = 1
    page_max = max(1, (len(reports) + page_size - 1) // page_size)
    while True:
        start = (page - 1) * page_size
        entries = [report[0] for report in reports[start:start + page_size]] or ["No squad reports."]
        pv.printPOV(
            matchInfo, *matchInfo.pov.pos,
            command_text="Reports: 'n' next | 'p' previous | 'x' exit",
            right_panel=(f"REPORTS {page}/{page_max}", entries),
        )
        choice = input("Reports: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "n" and page < page_max:
            page += 1
        elif choice == "p" and page > 1:
            page -= 1
        else:
            print("Choose 'n', 'p', or 'x'.")


def unreadReportMenu(matchInfo):
    """Display unread reports in the right panel and mark them as read."""
    unread = [report for report in matchInfo.pov.squad.reportLog if not report[2]]
    for report in unread:
        report[2] = True
    entries = [report[0] for report in unread] or ["No unread reports."]
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Unread reports: 'Enter' or 'x' return",
        right_panel=("UNREAD REPORTS", entries),
    )
    input("Unread reports: ")


def helpCommand(matchInfo):
    """Show a concise reference for every command accepted at the main prompt."""
    print("Main commands:")
    print("'q' 'w' 'e' 'a' 's' 'd' 'z' 'c' — move in the matching direction.")
    print("'f' — fire the selected weapon at the nearest tracked contact; menus offer more targeting choices.")
    print("'fire' — choose the default weapon used by 'f'.")
    print("'r' or 'radar' — toggle continuous active radar; it has an energy cost each turn.")
    print("'p' — send a one-turn active-radar pulse.")
    print("'ab' or 'abilities' — open the active mech's hull abilities.")
    print("'eject' — abandon the active mech and resolve pilot survival odds.")
    print("'flee' — leave from a border tile intact, or order the squad to withdraw.")
    print("'look' or 'l' — inspect the tactical view around map coordinates.")
    print("'m' — open the strategic map for radar contacts and map display controls.")
    print("'st' or 'status' — reopen the default tactical status panel.")
    print("'sq' or 'squad' — show squad readiness, roster, and switching options.")
    print("Squad menu: 'a' AI/manual control; 'o' give a friendly AI squad orders; 'v' automatic travel.")
    print("'auto' — toggle automatic followers after manual squad-leader movement; follows roads and warns about energy/stragglers.")
    print("'rep1' — show unread reports. 'rep' — open the full report log.")
    print("'o' or 'options' — change display options, including tactical width and height.")
    print("'n' or 'next' — switch to another mech in the active squad without ending its turn.")
    print("'end' — hand the squad turn to the next squad.")
    print("'?' — show this command reference.")
    print("Context menus always list their own available keys; use 'x' to cancel where offered.")
    matchInfo.advTurn = False
