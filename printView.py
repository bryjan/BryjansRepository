import termcolor
import printHUD as ph
import textwrap
from mechgame.coordinates import get_coordinate_input
from mechgame.mechs import MAX_HULL_ART_HEIGHT
from mechgame import radar

SIDE_PANEL_WIDTH = 34
# A damaged mortar Lancer is the tallest current detail set. Reserve space
# for its cockpit warning and the largest allowed hull art, then round up to
# an odd dimension so the tactical camera can stay centered.
MAX_STATUS_DETAIL_ROWS = 13
_minimum_side_panel_rows = MAX_HULL_ART_HEIGHT + 2 + MAX_STATUS_DETAIL_ROWS
MIN_TACTICAL_HEIGHT = (
    _minimum_side_panel_rows
    if _minimum_side_panel_rows % 2 else _minimum_side_panel_rows + 1
)


def _print_panel_text(text, width):
    """Print wrapped panel text without exceeding the tactical-map width."""
    for line in textwrap.wrap(text, width=width) or [""]:
        print(f"|{line:<{width}}|")


def _print_tactical_footer(width):
    """Print the command row in a standalone frame for menu-only callers."""
    divider = "+" + ("-" * width) + "+"
    print(divider)
    _print_panel_text("'f' Fire | 'r' Toggle Radar | 'rd' Contacts | 'ab' Abilities | 'sq' Squad | 'o' Options | 'n' Next | '?' Help | 'end' End Turn", width)
    print(divider)


def _condition_color(condition):
    """Choose an immediately readable color for a mech's average condition."""
    if condition <= 34:
        return "red"
    if condition <= 66:
        return "yellow"
    return "green"


def _centered_art_lines(mech_art, width, color):
    """Return one centered hull silhouette without exposing extra statistics."""
    lines = []
    for art_line in mech_art:
        left_padding = (width - len(art_line)) // 2
        right_padding = width - len(art_line) - left_padding
        lines.append(
            f"|{' ' * left_padding}{termcolor.colored(art_line, color)}{' ' * right_padding}|"
        )
    return lines


def _centered_mech_lines(mech, width):
    """Return the active mech's hull art, colored by average condition."""
    return _centered_art_lines(
        mech.mechClass.hull.asciiArt,
        width,
        _condition_color(mech.mechClass.condition),
    )


def _weapon_status(weapon):
    """Describe one weapon and its usable ammunition for the side panel."""
    if weapon.isLauncher:
        ammunition = ", ".join(
            f"{ammo.name} {ammo.charges}/{ammo.maxCharges}"
            if ammo.charges is not None else f"{ammo.name} Unlimited"
            for ammo in weapon.ammoTypes
        )
    else:
        ammunition = (
            "Unlimited" if weapon.charges is None
            else f"{weapon.charges}/{weapon.maxCharges}"
        )
    return f"{weapon.name}: {ammunition}"


def _panel_text_lines(text, width):
    """Wrap one status entry into already-bordered side-panel rows."""
    return [f"|{line:<{width}}|" for line in textwrap.wrap(text, width=width) or [""]]


def _finish_panel_lines(lines, height, width):
    """Clip low-priority rows and pad the panel to match the map height."""
    lines = lines[:height]
    return lines + [f"|{'':<{width}}|" for _ in range(height - len(lines))]


def menu_panel_lines(title, entries, height, width=SIDE_PANEL_WIDTH):
    """Build a temporary right-panel menu with a title and wrapped entries."""
    lines = [
        f"|{title[:width]:^{width}}|",
        "+" + ("-" * width) + "+",
    ]
    for entry in entries:
        lines.extend(_panel_text_lines(entry, width))
    return _finish_panel_lines(lines, height, width)


def _own_mech_panel_lines(mech, height, width):
    """Build the status/weapon fallback when the team tracks no enemies."""
    abilities = ", ".join(
        f"{ability.name} {'Unlimited' if ability.maxCharges is None else f'{ability.charges}/{ability.maxCharges}'}"
        for ability in mech.mechClass.hull.abilities
    ) or "None"
    weakest_limb = min(mech.mechClass.limbList, key=lambda limb: limb.limbCon)
    weakest_condition = round(weakest_limb.limbCon * 100)
    entries = [
        f"Condition: {round(mech.mechClass.condition)}%",
        f"Most damaged: {weakest_limb.name} ({weakest_condition}%)",
    ]
    if mech.cockpit.status < 2:
        pilot_condition = "Injured" if mech.cockpit.status == 1 else "Lost"
        entries.append(f"Pilot: {pilot_condition} (cockpit damaged)")
    entries.extend([
        f"AP: {mech.ap}/{mech.mechClass.apMax} | MP: {mech.mp}/{mech.mechClass.mpMax}",
        f"Energy: {mech.energy}/{mech.mechClass.energyMax} | Regen: {mech.mechClass.energyGen}",
        "Weapons:",
        *(_weapon_status(weapon) for weapon in mech.mechClass.gunList),
        f"Abilities: {abilities}",
        f"Radar: {'ON' if mech.radarOn else 'OFF'} | Speed: {mech.speed}",
    ])
    # The upper block stays visually stable: silhouette, breathing room,
    # centered identity, then a right-panel-only divider before live details.
    identity = f"{mech.pilot.name} - {mech.mechClass.name}"[:width]
    lines = [
        *_centered_mech_lines(mech, width),
        f"|{identity:^{width}}|",
        "+" + ("-" * width) + "+",
    ]
    for entry in entries:
        lines.extend(_panel_text_lines(entry, width))
    return _finish_panel_lines(lines, height, width)


def _focused_contact_panel_lines(matchInfo, contacts, focus, height, width):
    """Build a sensor-limited target view plus a compact contact list."""
    observer = matchInfo.pov
    detail = radar.contact_details(observer, matchInfo, focus)
    identity = f"FOCUS: {detail['classification']}"[:width]
    lines = []
    # Hull art is only safe to show once visual confirmation or radar level 3
    # identifies the chassis. It is deliberately white: condition is unknown.
    if detail["silhouette_known"]:
        lines.extend(_centered_art_lines(focus.mechClass.hull.asciiArt, width, "white"))
    lines.extend([
        f"|{identity:^{width}}|",
        "+" + ("-" * width) + "+",
    ])
    sensor_source = "Visual" if detail["visually_confirmed"] else f"Radar ID {detail['radar_level']}"
    entries = [
        f"Position: {detail['position']} | Distance: {detail['distance']:.1f}",
        f"Movement: {detail['movement']}",
        f"Sensors: {sensor_source}",
        f"Return: {detail['return_power']} / {detail['threshold']}",
        "Tracked contacts:",
    ]
    for contact in contacts:
        contact_detail = radar.contact_details(observer, matchInfo, contact)
        marker = ">" if contact is focus else "-"
        entries.append(
            f"{marker} {contact_detail['classification']} {contact_detail['position']} "
            f"({contact_detail['distance']:.1f})"
        )
    for entry in entries:
        lines.extend(_panel_text_lines(entry, width))
    return _finish_panel_lines(lines, height, width)


def _side_panel_lines(matchInfo, height, width=SIDE_PANEL_WIDTH):
    """Show contact intelligence first, falling back to own weapon readiness."""
    observer = matchInfo.pov
    contacts = radar.tracked_contacts(observer)
    focus = radar.panel_focus(observer)
    if focus is not None:
        return _focused_contact_panel_lines(matchInfo, contacts, focus, height, width)
    return _own_mech_panel_lines(observer, height, width)


def _hud_lines(matchInfo, width):
    """Build the stable, full-width resource HUD shown above the tactical view."""
    mech = matchInfo.pov
    condition = round(mech.mechClass.condition)
    terrain = matchInfo.map[mech.pos[1]][mech.pos[0]].terrain.name
    entries = [
        f"HUD | {mech.pilot.name} | Pos: {mech.pos} | {condition}% | Tile: {terrain}",
        (
            f"AP {mech.ap}/{mech.mechClass.apMax} | MP {mech.mp}/{mech.mechClass.mpMax} | "
            f"EN {mech.energy}/{mech.mechClass.energyMax} +{mech.mechClass.energyGen} | "
            f"SPD {mech.speed} | RADAR {'ON' if mech.radarOn else 'OFF'}"
        ),
    ]
    lines = []
    for entry in entries:
        # A wrapped command separator can otherwise begin the next row with
        # ``|`` and look like a second left-hand border.
        lines.extend(line.lstrip("| ") for line in textwrap.wrap(entry, width=width) or [""])
    return lines


def _command_lines(width, command_text=None):
    """Build either the normal commands or the active menu's available keys."""
    if command_text is None:
        command_text = (
            "Commands | 'f' Fire | 'r' Toggle Radar | 'rd' Contacts | 'ab' Abilities | 'sq' Squad | "
            "'o' Options | 'n' Next | '?' Help | 'end' End Turn"
        )
    # Separators may land at a wrap boundary; trimming both edges prevents a
    # separator from visually merging with the panel's actual border.
    return [line.strip("| ") for line in textwrap.wrap(command_text, width=width)]

def printPOV(matchInfo, povX, povY, command_text=None, right_panel=None):
    """Render a rectangular tactical window centered on the supplied map position."""
    from mechgame.terrain import Cell

    # Critical reports remain above the console so urgent combat information
    # is never buried by the regularly refreshed tactical display.
    ph.criticalReports(matchInfo)

    # Small maps should not look empty merely because one requested dimension
    # exceeds the generated world. Each dimension stays odd so the point of
    # view remains centered independently on both axes.
    windowWidth = min(matchInfo.windowWidth, matchInfo.mapWidth)
    windowHeight = min(matchInfo.windowHeight, matchInfo.mapHeight)
    if windowWidth % 2 == 0:
        windowWidth -= 1
    if windowHeight % 2 == 0:
        windowHeight -= 1
    widthExtend = (windowWidth - 1) // 2
    heightExtend = (windowHeight - 1) // 2

    # Make the rectangular cell window.
    mapWindow = []
    xRow = []
    y = povY - heightExtend
    while y <= povY + heightExtend:
        x = povX - widthExtend
        while x <= povX + widthExtend:
            if y < 0 or y >= matchInfo.mapHeight or x < 0 or x >= matchInfo.mapWidth:
                # Mark space beyond the generated world as a border rather
                # than blank terrain, making map limits immediately obvious.
                xRow.append(Cell(matchInfo.border,[x, y]))
            else:
                xRow.append(matchInfo.map[y][x])
            x += 1
        # Tactical coordinates use a Cartesian convention: larger Y values are
        # farther north and therefore appear higher on the displayed map.
        mapWindow.insert(0, xRow)
        y += 1
        xRow = []

    
    # Each map cell renders as a symbol plus one trailing space, so the frame
    # width scales with the configured horizontal view dimension.
    panelWidth = windowWidth * 2
    topDivider = "+" + ("-" * panelWidth) + "+" + ("-" * SIDE_PANEL_WIDTH) + "+"
    fullPanelWidth = panelWidth + SIDE_PANEL_WIDTH + 1
    fullDivider = "+" + ("-" * fullPanelWidth) + "+"
    sideLines = (
        menu_panel_lines(right_panel[0], right_panel[1], windowHeight)
        if right_panel is not None else _side_panel_lines(matchInfo, windowHeight)
    )
    # The HUD remains in one dependable place above the map, independent of
    # how much detail the active mech panel can fit at this window height.
    print(fullDivider)
    for line in _hud_lines(matchInfo, fullPanelWidth):
        print(f"|{line:<{fullPanelWidth}}|")
    # This segmented edge simultaneously closes the HUD and opens the map and
    # active-mech panels, keeping the entire console in one shared frame.
    print(topDivider)
    for row, sideLine in zip(mapWindow, sideLines):
        print("|", end="")
        for cell in row:
            if cell.terrain == matchInfo.border:
                cell.terrain.displayTerrain() #display borders
            elif cell.canSee == True:
                    cell.displayCell(matchInfo) #already anticipates entities on cell, will display entity if visible
            elif cell.radarReturn == True:
                    cell.displayRadarReturn(matchInfo)
            else:
                 print(" ", end = " ")
        print(sideLine)
    # This shared divider closes both upper panels and opens the command bar.
    print(fullDivider)
    for line in _command_lines(fullPanelWidth, command_text):
        print(f"|{line:<{fullPanelWidth}}|")
    print(fullDivider)
    return
    
def lookAt(matchInfo): #TODO parse text to make input smoother
    """Prompt for a coordinate and display the tactical view around it."""
    
    coord = get_coordinate_input(matchInfo, "View coordinates")
    printPOV(matchInfo, coord[0], coord[1])
        
    return input("Press 'Enter' to return")
