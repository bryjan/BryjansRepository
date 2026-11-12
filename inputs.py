import printView as pv
import functions as f


def _read_nonempty(prompt):
    """Read a trimmed command or menu value, rejecting blank input."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print()


def receive_input(matchInfo):
    """Read one player command and dispatch it to the relevant game action."""
    playerInput = _read_nonempty("Input: ").lower()

    match playerInput:
    
        case "?":
            return helpCommand(matchInfo)
        
        case "rep":
            return printReportLogPrompt(matchInfo)
        
        case "rep1":
            return printReportLog(matchInfo)
        
        case "next":
            return matchInfo.nextMechinTeam()
        
        case "q" | "w" | "e" | "a" | "s" | "d" | "z" | "c":
            return matchInfo.pov.moveMech(matchInfo, playerInput)
        
        case "r":
            return matchInfo.pov.toggleRadar(matchInfo)

        case "p":
            return matchInfo.pov.pulseRadar(matchInfo)
        
        case "end":
            # This is the sole command that hands control to the next squad.
            matchInfo.turnEnded = True
            return
            
        case "look" | "l":
            return pv.lookAt(matchInfo)
        
        case "fire":
            return gunMenu(matchInfo)
        
        case "f" | "F":
            return fire(matchInfo)
        
        case _:
            print("Input not recognized. Try again.")
            return
    

def recieveInput(matchInfo):
    """Compatibility wrapper for the original misspelled command function."""
    return receive_input(matchInfo)

def fire(matchInfo):
    """Fire the selected default weapon at a tactical-menu target."""
    mech = matchInfo.pov
    gunList = mech.mechClass.gunList

    if len(gunList) == 0:
        print("You have no weapons.")
        return
    
    defaultGuns = 0
    for limb in gunList:
        if limb.defaultGun == True:
            defaultGuns += 1
            gun = limb

    if defaultGuns < 1 or defaultGuns > 1:
        print("Select a default weapon.")
        return gunMenu(matchInfo)
    
    targetPos = chooseFireTarget(matchInfo)
    if targetPos is None:
        return
    gun.shootAt(matchInfo, targetPos)


def chooseFireTarget(matchInfo):
    """Offer visible, remembered, and manual targeting without defaulting to text coordinates."""
    mech = matchInfo.pov
    print("Fire target: [t]racked enemy  [l]ast fired location  [c]oordinates  [x] cancel")
    choice = _read_nonempty("Target: ").lower()

    if choice == "x":
        return None
    if choice == "c":
        target = f.getCoordinateInput(matchInfo, "Enter coordinates to shoot at")
        return None if target == "x" else target
    if choice == "l":
        if mech.lastFiredAt is None:
            print("No previous firing location.")
            return None
        return list(mech.lastFiredAt)
    if choice not in ("t", "v"):
        print("Choose t, l, c, or x.")
        return None
    if not mech.trackedEnemies:
        print("No enemy mechs are currently tracked.")
        return None
    if len(mech.trackedEnemies) == 1:
        return list(mech.trackedEnemies[0].pos)

    for index, enemy in enumerate(mech.trackedEnemies, start=1):
        print(f"{index}. {enemy.pilot.name} — {enemy.mechClass.name} at {enemy.pos}")
    selection = _read_nonempty("Tracked target: ")
    if not selection.isdigit() or not 1 <= int(selection) <= len(mech.trackedEnemies):
        print("Choose a listed target number.")
        return None
    return list(mech.trackedEnemies[int(selection) - 1].pos)

def gunMenu(matchInfo): #TODO add ability to exit
    """Display weapons and make one available as the default firing choice."""

    mech = matchInfo.pov
    gunList = mech.mechClass.gunList

    if len(gunList) == 1:
        gunList[0].defaultGun = True
        print(gunList[0].printShortDesc())
        print("You only have one weapon availble to (f)ire. It is set to your default weapon.")
        return
    elif len(gunList) == 0:
        print("You have no weapons.")
        return


    menuWidth = 0
    for limb in gunList:
        limb.defaultGun = False
        if len(limb.printShortDesc()) > menuWidth:
            menuWidth = len(limb.printShortDesc())
    menuWidth += 4
    
    menuDivider = ""
    i = 1
    while i <= menuWidth:
        i+=1
        menuDivider = f"{menuDivider}-" 

    print("Select a weapon to (f)ire by default.")
    for limb in gunList:
        print(menuDivider)
        print(f"{limb.printShortDesc()} | {gunList.index(limb) + 1}")
    print(menuDivider)

    #get default gun choice from menu
    #TODO add ability to pull a weapon's long description
    playerInput = _read_nonempty("Choose default gun: ")

    try:
        playerInput = int(playerInput)
        if not 1 <= playerInput <= len(gunList):
            print("Please enter an integer listed in the menu.")
            gunMenu(matchInfo)
        else:
            gunList[playerInput - 1].defaultGun = True
            print(f"{gunList[playerInput - 1].name} set to (f)ire by default")
            return
    except ValueError:
        print("Please enter an integer.")
        gunMenu(matchInfo)


def nextMech(matchInfo):
    matchInfo.nextMechinTeam()

def printReportLogPrompt(matchInfo):
    """Ask for a report-log page before rendering it."""
    inpPage = input("Page number: ")
    if inpPage.isdigit():
        inpPage = int(inpPage)
    if type(inpPage) != int:
        return print(f" {inpPage} is not a valid page number.")
    printReportLog(matchInfo, page=int(inpPage))

def printReportLog(matchInfo,page=1):
    """Print one fixed-size page of the current squad's reports."""
    mech = matchInfo.pov
    matchInfo.advTurn = False
    pageTotal = len(mech.squad.reportLog)
    pageSize = 40
    pageMax = (pageTotal/pageSize)+1
    pageNum = page
    if pageNum > pageMax:
        print("There is only "+str(int(pageMax))+" pages of reports")
        print()
        return
    numrep = 0
    print(f"Report Log Page: {pageNum}")
    for rep in mech.squad.reportLog[(pageNum * pageSize) - pageSize:(pageNum * pageSize)]:
        print (rep[0])
        numrep+=1
        if numrep > pageSize:
            return
    print()

def printUnreads(matchInfo):
    """Print unread squad reports and mark each displayed entry as read."""
    mech = matchInfo.pov
    matchInfo.advTurn = False
    pageSize = 100
    numrep = 0
    for rep in mech.squad.reportLog:
        if rep[2] == False:
            print (rep[0])
            rep[2] = True
        numrep+=1
        if numrep > pageSize:
            return
    print()

def helpCommand(matchInfo): #TODO update with all commands
    """Show the currently supported command shortcuts."""
    print ("Here are the list of commands available to you:")
    print ("Use 'w,a,s,d' and their diagonals 'q,e,z,c' to move the mech")
    print ("Type 'r' to toggle continuous radar; it costs energy to start and each turn it stays on")
    print ("Type 'p' for a one-turn radar pulse; it costs energy once and shuts off at turn end")
    print ("Type 'f' to fire: choose a tracked enemy, your last firing location, or coordinates")
    print ("Type 'rep1' to see unread reports, 'rep' will prompt you for a full report-log page")
    print ("Type 'next' to switch to the next mech in you squad")
    matchInfo.advTurn = False

