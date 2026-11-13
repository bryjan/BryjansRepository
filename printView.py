import termcolor
import printHUD as ph
import textwrap
from mechgame.coordinates import get_coordinate_input


def _print_panel_text(text, width):
    """Print wrapped panel text without exceeding the tactical-map width."""
    for line in textwrap.wrap(text, width=width) or [""]:
        print(f"|{line:<{width}}|")


def _print_tactical_footer(width):
    """Show the most useful options and log commands below the map frame."""
    divider = "+" + ("-" * width) + "+"
    print(divider)
    _print_panel_text("'f' Fire | 'rd' Radar | 'ab' Abilities | 'sq' Squad | 'n' Next | '?' Help | 'end' End Turn", width)
    print(divider)

def printPOV(matchInfo, povX, povY):
    """Render a rectangular tactical window centered on the supplied map position."""
    from mechgame.terrain import Cell

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
    divider = "+" + ("-" * panelWidth) + "+"
    print(divider)
    for y in mapWindow:
        print("|", end="")
        for cell in y:
            if cell.terrain == matchInfo.border:
                cell.terrain.displayTerrain() #display borders
            elif cell.canSee == True:
                    cell.displayCell(matchInfo) #already anticipates entities on cell, will display entity if visible
            elif cell.radarReturn == True:
                    cell.displayRadarReturn(matchInfo)
            else:
                 print(" ", end = " ")
        print("|")
    _print_tactical_footer(panelWidth)
    return
    
def lookAt(matchInfo): #TODO parse text to make input smoother
    """Prompt for a coordinate and display the tactical view around it."""
    
    coord = get_coordinate_input(matchInfo, "View coordinates")
    ph.displayHUD(matchInfo)
    printPOV(matchInfo, coord[0], coord[1])
        
    return input("Press 'Enter' to return")
