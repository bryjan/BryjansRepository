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
    _print_panel_text("Options: 'f' fire | 'rd' radar | 'ab' abilities | 'sq' squad | 'o' options | '?' help | 'end' turn", width)
    print(divider)

def printPOV(matchInfo, povX, povY):
    """Render a square tactical window centered on the supplied map position."""
    from mechgame.terrain import Cell

    #makes window
    mapWindow = []

    # A small map should not look empty simply because the normal tactical
    # window is larger than one of its dimensions. Keep the displayed window
    # odd so the active coordinate remains centered.
    windowSize = min(matchInfo.windowSize, matchInfo.mapWidth, matchInfo.mapHeight)
    if windowSize % 2 == 0:
        windowSize -= 1
    windowExtend = windowSize - 1
    windowExtend = int(windowExtend / 2) #half the window size extended from the center will make up the window

    xRow = []
    y = povY - windowExtend
    while y <= povY + windowExtend:
        x = povX - windowExtend
        while x <= povX + windowExtend:
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
    # width scales with the configured tactical window rather than map size.
    panelWidth = windowSize * 2
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
