import functions as f
import termcolor
import printHUD as ph
import textwrap


def _print_panel_text(text, width):
    """Print wrapped panel text without exceeding the tactical-map width."""
    for line in textwrap.wrap(text, width=width) or [""]:
        print(f"|{line:<{width}}|")


def _print_tactical_footer(width):
    """Show the most useful options and log commands below the map frame."""
    divider = "+" + ("-" * width) + "+"
    print(divider)
    _print_panel_text("Options: f fire | fire change weapon | st status | sq squad | ? help | end turn", width)
    _print_panel_text("Logs: rep1 unread reports | rep report pages", width)
    print(divider)

def printPOV(matchInfo, povX, povY):
    """Render a square tactical window centered on the supplied map position."""
    from mechgame.terrain import Cell

    #makes window
    mapWindow = []

    # ensure window is odd.
    if matchInfo.windowSize % 2 == 0:
        matchInfo.windowSize += 1
    windowExtend = matchInfo.windowSize - 1
    windowExtend = int(windowExtend / 2) #half the window size extended from the center will make up the window

    xRow = []
    y = povY - windowExtend
    while y <= povY + windowExtend:
        x = povX - windowExtend
        while x <= povX + windowExtend:
            if y < 0 or y > matchInfo.mapSize - 1 or x < 0 or x > matchInfo.mapSize - 1:
                # Reuse the match's terrain catalogue instead of constructing
                # equivalent blank and border terrain objects for every frame.
                xRow.append(Cell(matchInfo.blank,[x, y]))
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
    panelWidth = matchInfo.windowSize * 2
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
    
    coord = f.getCoordinateInput(matchInfo, "View coordinates")
    ph.displayHUD(matchInfo)
    printPOV(matchInfo, coord[0], coord[1])
        
    return input("Press enter to return")
