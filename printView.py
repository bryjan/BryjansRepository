import termcolor
import printHUD as ph
import textwrap
from mechgame.coordinates import get_coordinate_input

SIDE_PANEL_WIDTH = 34


def _print_panel_text(text, width):
    """Print wrapped panel text without exceeding the tactical-map width."""
    for line in textwrap.wrap(text, width=width) or [""]:
        print(f"|{line:<{width}}|")


def _print_tactical_footer(width):
    """Print the command row in a standalone frame for menu-only callers."""
    divider = "+" + ("-" * width) + "+"
    print(divider)
    _print_panel_text("'f' Fire | 'rd' Radar | 'ab' Abilities | 'sq' Squad | 'n' Next | '?' Help | 'end' End Turn", width)
    print(divider)


def _condition_color(condition):
    """Choose an immediately readable color for a mech's average condition."""
    if condition <= 34:
        return "red"
    if condition <= 66:
        return "yellow"
    return "green"


def _centered_mech_lines(condition, width):
    """Return a tiny mech silhouette, centered and colored by condition."""
    mech_art = (" /\\ ", "/##\\", " /\\ ")
    color = _condition_color(condition)
    lines = []
    for art_line in mech_art:
        left_padding = (width - len(art_line)) // 2
        right_padding = width - len(art_line) - left_padding
        lines.append(
            f"|{' ' * left_padding}{termcolor.colored(art_line, color)}{' ' * right_padding}|"
        )
    return lines


def _side_panel_lines(matchInfo, height, width=SIDE_PANEL_WIDTH):
    """Build a fixed-height active-mech summary for the tactical side panel."""
    mech = matchInfo.pov
    default_weapon = next(
        (weapon.name for weapon in mech.mechClass.gunList if weapon.defaultGun),
        "None selected",
    )
    abilities = ", ".join(
        f"{ability.name} {'∞' if ability.maxCharges is None else f'{ability.charges}/{ability.maxCharges}'}"
        for ability in mech.mechClass.hull.abilities
    ) or "None"
    entries = [
        f"{mech.pilot.name} - {mech.mechClass.name}",
        f"Condition: {round(mech.mechClass.condition)}%",
        f"Position: {mech.pos}",
        f"AP: {mech.ap}/{mech.mechClass.apMax} | MP: {mech.mp}/{mech.mechClass.mpMax}",
        f"Energy: {mech.energy}/{mech.mechClass.energyMax} | Regen: {mech.mechClass.energyGen}",
        f"Radar: {'ON' if mech.radarOn else 'OFF'} | Speed: {mech.speed}",
        f"Weapon: {default_weapon}",
        f"Abilities: {abilities}",
    ]
    lines = _centered_mech_lines(mech.mechClass.condition, width)
    for entry in entries:
        lines.extend(f"|{line:<{width}}|" for line in textwrap.wrap(entry, width=width) or [""])
    lines = lines[:height]
    return lines + [f"|{'':<{width}}|" for _ in range(height - len(lines))]


def _hud_lines(matchInfo, width):
    """Build the full-width resource and command panel beneath the tactical view."""
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
        "Commands | 'f' Fire | 'rd' Radar | 'ab' Abilities | 'sq' Squad | 'n' Next | '?' Help | 'end' End Turn",
    ]
    lines = []
    for entry in entries:
        lines.extend(textwrap.wrap(entry, width=width) or [""])
    return lines

def printPOV(matchInfo, povX, povY):
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
    sideLines = _side_panel_lines(matchInfo, windowHeight)
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
    # This shared divider closes both upper panels and opens the HUD panel.
    print(fullDivider)
    for line in _hud_lines(matchInfo, fullPanelWidth):
        print(f"|{line:<{fullPanelWidth}}|")
    print(fullDivider)
    return
    
def lookAt(matchInfo): #TODO parse text to make input smoother
    """Prompt for a coordinate and display the tactical view around it."""
    
    coord = get_coordinate_input(matchInfo, "View coordinates")
    printPOV(matchInfo, coord[0], coord[1])
        
    return input("Press 'Enter' to return")
