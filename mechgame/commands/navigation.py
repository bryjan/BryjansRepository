"""Commands for local movement support, viewing, and hull abilities."""

from ..ui import tactical as pv
from .. import radar

from ..coordinates import get_coordinate_input
from .firing import fire


def radarToggle(matchInfo):
    """Toggle the active scanner, retaining a helper for simple callers."""
    mech = matchInfo.pov
    if hasattr(mech, "toggleRadar"):
        return mech.toggleRadar(matchInfo)
    # Lightweight callers such as command tests may only supply a radar flag.
    mech.radarOn = not mech.radarOn


def lookAt(matchInfo):
    """Prompt for a coordinate and render the tactical view around it."""
    coordinate = get_coordinate_input(matchInfo, "View coordinates")
    if coordinate == "x":
        return
    pv.printPOV(matchInfo, *coordinate)
    input("Press 'Enter' to return")


def mapView(matchInfo):
    """Open strategic-map controls without crowding the combat command bar."""
    while True:
        pv.print_overview(
            matchInfo,
            command_text="Map: 'r' radar contacts | 'd' debug options | 'x' return",
        )
        choice = input("Map: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "d":
            debugMapMenu(matchInfo)
            continue
        if choice == "r":
            radarMenu(matchInfo)
            continue
        print("Choose 'r', 'd', or 'x'.")


def debugMapMenu(matchInfo):
    """Keep temporary map-inspection controls out of the normal map menu."""
    while True:
        visibility = matchInfo.pov.team.mapVisibility
        tactical_state = "ON" if matchInfo.showTacticalLocations else "OFF"
        fog_state = "OFF" if visibility.show_all_terrain else "ON"
        reveal_state = "ON" if visibility.debug_reveal_all else "OFF"
        entries = [
            f"'t' Tactical markers: {tactical_state}",
            f"'f' Fog of war: {fog_state}",
            f"'v' Reveal unseen units: {reveal_state}",
        ]
        pv.print_overview(
            matchInfo,
            command_text="Debug: 't' markers | 'f' fog | 'v' reveal all | 'x' return to map",
            right_panel=("MAP DEBUG", entries),
        )
        choice = input("Map debug: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "t":
            matchInfo.showTacticalLocations = not matchInfo.showTacticalLocations
            continue
        if choice == "f":
            visibility.show_all_terrain = not visibility.show_all_terrain
            continue
        if choice == "v":
            visibility.debug_reveal_all = not visibility.debug_reveal_all
            continue
        print("Choose 't', 'f', 'v', or 'x'.")


def radarMenu(matchInfo):
    """Browse shared radar contacts over the strategic map."""
    observer = matchInfo.pov
    contacts = radar.team_contacts(observer)
    entries = []
    for index, contact in enumerate(contacts, start=1):
        detail = radar.contact_details(observer, matchInfo, contact)
        entries.append(
            f"'{index}' {detail['classification']} at {detail['position']} "
            f"| {detail['distance']:.1f} tiles"
        )
    if not entries:
        entries.append("No enemy radar contacts are currently shared with your team.")

    pv.print_overview(
        matchInfo,
        command_text="Radar: enter a listed contact number | 'x' return to map",
        right_panel=("TEAM RADAR — NEAREST FIRST", entries),
    )
    selection = input("Radar contact ('x' to return): ").strip().lower()
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
    pv.print_overview(
        matchInfo,
        command_text="Radar contact: 'f' fire at this contact | 'x' return to map",
        right_panel=("RADAR CONTACT", detail_entries),
    )
    action = input("Radar contact: ").strip().lower()
    if action == "f":
        return fire(matchInfo, selected_target)
    if action not in ("", "x"):
        print("Choose 'f' or 'x'.")


def statusPanel(matchInfo):
    """Open the normal tactical view as an explicit status reference."""
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Status: 'Enter' or 'x' return",
    )
    input("Status: ")


def abilityMenu(matchInfo):
    """Select and activate one of the active mech's hull-mounted abilities."""
    mech = matchInfo.pov
    abilities = mech.mechClass.hull.abilities
    if not abilities:
        print("This mech has no hull abilities.")
        return

    entries = [
        f"'{index}' {ability.short_description()}"
        for index, ability in enumerate(abilities, start=1)
    ]
    pv.printPOV(
        matchInfo, *mech.pos,
        command_text="Abilities: enter a listed number | 'x' cancel",
        right_panel=("HULL ABILITIES", entries),
    )
    choice = input("Ability ('x' to cancel): ").strip().lower()
    if choice in ("", "x"):
        return
    if not choice.isdigit() or not 1 <= int(choice) <= len(abilities):
        print("Choose a listed ability number or 'x'.")
        return

    ability = abilities[int(choice) - 1]
    direction = None
    if ability.requiresDirection:
        pv.printPOV(
            matchInfo, *mech.pos,
            command_text="Dash direction: 'q' 'w' 'e' 'a' 's' 'd' 'z' 'c' | 'x' cancel",
            right_panel=("HULL ABILITIES", entries),
        )
        direction = input(
            "Dash direction ('q', 'w', 'e', 'a', 's', 'd', 'z', or 'c'; 'x' to cancel): "
        ).strip().lower()
        if direction == "x":
            return
    ability.use(matchInfo, mech, direction)
