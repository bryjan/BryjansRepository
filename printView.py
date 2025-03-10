import gameClasses as C
import functions as f
import termcolor
import printHUD as ph

def printPOV(matchInfo, povX, povY):

    blank = C.TerrainType("blank", " ", "black", size= 0, moveCostBySize = [], visualAbsorbtion = 9999, radarAbsorbtion = 9999, fireproof = True, passable = False)
    border = C.TerrainType("border", "X", "white", size= 0, moveCostBySize = [9999,9999,9999,9999,9999,9999,9999], visualAbsorbtion = 1, radarAbsorbtion =1, radarSig = 1, fireproof = True, passable = False)
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
                xRow.append(C.Cell(blank,[x, y]))
            else:
                xRow.append(matchInfo.map[y][x])
            x += 1
        mapWindow.insert(0, xRow)
        y += 1
        xRow = []

    
    #print window
    for y in mapWindow:
        for cell in y:
            if cell.terrain == border:
                cell.terrain.displayTerrain() #display borders
            elif cell.canSee == True:
                    cell.displayCell(matchInfo) #already anticipates entities on cell, will display entity if visible
            elif cell.radarReturn == True:
                    cell.displayRadarReturn(matchInfo)
            else:
                 print(" ", end = " ")
        print()
    return
    
def lookAt(matchInfo): #TODO parse text to make input smoother
    
    coord = f.getCoordinateInput(matchInfo, "View coordinates")
    ph.displayHUD(matchInfo)
    printPOV(matchInfo, coord[0], coord[1])
        
    return input("Press enter to return")
