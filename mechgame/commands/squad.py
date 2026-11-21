"""Commands for squad management, radar contacts, reports, and options."""

from ..ui import tactical as pv

from .. import radar
from .firing import fire
from .shared import read_nonempty


def _print_options_panel(matchInfo, command_text):
    """Render live display options inside the tactical command bar."""
    pv.printPOV(matchInfo, *matchInfo.pov.pos, command_text=command_text)


def squadMenu(matchInfo):
    """Show squad readiness and roster before player-facing squad controls."""
    squad = matchInfo.pov.squad
    entries = [*squad.statusReport().splitlines(), *squad.rosterReport().splitlines()]
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Squad: 'm' switch mech | 's' switch controllable squad | 'x' exit",
        right_panel=("SQUAD", entries),
    )
    choice = input("Squad: ").strip().lower()

    if choice in ("", "x"):
        return
    if choice == "m":
        return selectSquadMech(matchInfo, squad)
    if choice == "s":
        return selectControllableSquad(matchInfo)
    print("Choose 'm', 's', or 'x'.")


def radarMenu(matchInfo):
    """Show every friendly squad's radar contacts nearest to the active mech."""
    observer = matchInfo.pov
    contacts = radar.team_contacts(observer)
    if not contacts:
        print("No enemy radar contacts are currently shared with your team.")
        return

    entries = []
    for index, contact in enumerate(contacts, start=1):
        detail = radar.contact_details(observer, matchInfo, contact)
        entries.append(
            f"'{index}' {detail['classification']} at {detail['position']} "
            f"| {detail['distance']:.1f} tiles"
        )

    pv.printPOV(
        matchInfo, *observer.pos,
        command_text="Radar: enter a listed contact number | 'x' exit",
        right_panel=("TEAM RADAR — NEAREST FIRST", entries),
    )

    selection = input("Select a contact for details, or 'x' to exit: ").strip().lower()
    if selection in ("", "x"):
        return
    if not selection.isdigit() or not 1 <= int(selection) <= len(contacts):
        print("Choose a listed contact number or 'x'.")
        return

    selected_target = contacts[int(selection) - 1]
    observer.focusedEnemy = selected_target
    detail = radar.contact_details(observer, matchInfo, selected_target)
    confirmation = "yes" if detail["visually_confirmed"] else "no"
    detail_entries = [
        f"Classification: {detail['classification']}",
        f"Position: {detail['position']} | Distance: {detail['distance']:.1f} tiles",
        f"Movement: {detail['movement']} | Visually confirmed: {confirmation}",
        f"Radar return: {detail['return_power']} / {detail['threshold']} required",
    ]
    pv.printPOV(
        matchInfo, *detail["position"],
        command_text="Radar contact: 'f' fire at this contact | 'x' exit",
        right_panel=("RADAR CONTACT", detail_entries),
    )
    action = input("Radar contact: 'f' fire at this contact | 'x' exit: ").strip().lower()
    if action == "f":
        return fire(matchInfo, selected_target)
    if action not in ("", "x"):
        print("Choose 'f' or 'x'.")


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
        f"'{index}' {mech.pilot.name} — {mech.mechClass.name} ({round(mech.mechClass.condition)}%)"
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
    print("'rd' — view shared team radar contacts and fire at one.")
    print("'ab' or 'abilities' — open the active mech's hull abilities.")
    print("'look' or 'l' — inspect the tactical view around map coordinates.")
    print("'m' — open the shared strategic map; unexplored terrain remains hidden.")
    print("'st' or 'status' — reopen the default tactical status panel.")
    print("'sq' or 'squad' — show squad readiness, roster, and switching options.")
    print("'rep1' — show unread reports. 'rep' — open the full report log.")
    print("'o' or 'options' — change display options, including tactical width and height.")
    print("'n' or 'next' — switch to another mech in the active squad without ending its turn.")
    print("'end' — hand the squad turn to the next squad.")
    print("'?' — show this command reference.")
    print("Context menus always list their own available keys; use 'x' to cancel where offered.")
    matchInfo.advTurn = False
