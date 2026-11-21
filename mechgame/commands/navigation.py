"""Commands for local movement support, viewing, and hull abilities."""

from ..ui import tactical as pv

from ..coordinates import get_coordinate_input


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
    """Open the scaled strategic map and its tactical-location overlay."""
    while True:
        pv.print_overview(matchInfo)
        choice = input("Map overview ('t' tactical locations; 'Enter' or 'x' return): ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "t":
            matchInfo.showTacticalLocations = not matchInfo.showTacticalLocations
            continue
        print("Choose 't', 'Enter', or 'x'.")


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
