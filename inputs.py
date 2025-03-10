import printView as pv
import functions as f

def recieveInput(matchInfo):

    playerInput = ""
    while len(playerInput) == 0:
        playerInput = input("Input: ")
        print()

    if playerInput[0] == " ": #cleans up input from accidental spaces
        playerInput.pop(0)
    if playerInput[:-0] == " ":
        playerInput.pop(len(playerInput)-1)

    match playerInput:
    
        case "?":
            return helpCommand(matchInfo)
        
        case "rep":
            return printReportLogPrompt(matchInfo)
        
        case "rep1":
            return printReportLog(matchInfo)
        
        case "next" | "Next" | "NEXT":
            return matchInfo.nextMechinTeam()
        
        case "q" | "w" | "e" | "a" | "s" | "d" | "z" | "c":
            return matchInfo.pov.moveMech(matchInfo, playerInput)
        
        case "r":
            return printUnreads(matchInfo)
        
        case "end" | "End":
            return matchInfo.nextSquadTurn()
            
        case "look" | "l":
            return pv.lookAt(matchInfo)
        
        case "fire" | "Fire":
            return gunMenu(matchInfo)
        
        case "f" | "F":
            return fire(matchInfo)
        
        case "radar":
            return radarToggle(matchInfo)

        case _:
            print("Input not recognized. Try again.")
            return
    

def radarToggle(matchInfo):
    mech = matchInfo.pov
    if mech.radarOn == True:
        mech.radarOn == False
        print("Radar toggled off")
    else:
        mech.radarOn == True
        print("Radar toggled on")

def fire(matchInfo):
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
    
    targetPos = f.getCoordinateInput(matchInfo, "Enter coordinates to shoot at") #TODO give option to cancel
    if targetPos == "x":
        return
    gun.shootAt(matchInfo, targetPos)

def gunMenu(matchInfo): #TODO add ability to exit

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
    playerInput = ""
    playerInput = input("Choose default gun: ")
    while len(playerInput) == 0:
        playerInput = input("Choose default gun: ")
        print()

    if playerInput[0] == " ": #cleans up input from accidental spaces
        playerInput.pop(0)
    if playerInput[:-0] == " ":
        playerInput.pop(len(playerInput)-1)

    try:
        playerInput = int(playerInput)
        if playerInput < 0 or playerInput > len(gunList) + 1:
            print("Please enter an integer listed in the menu.")
            gunMenu(matchInfo)
        else:
            gunList[playerInput - 1].defaultGun = True
            print(f"{gunList[playerInput - 1].name} set to (f)ire by default")
            return
    except:
        print("Please enter an integer.")
        gunMenu(matchInfo)


def nextMech(matchInfo):
    matchInfo.nextMechinTeam()

def printReportLogPrompt(matchInfo):
    inpPage = input("Page number: ")
    if inpPage.isdigit():
        inpPage = int(inpPage)
    if type(inpPage) != int:
        return print(f" {inpPage} is not a valid page number.")
    printReportLog(matchInfo, page=int(inpPage))

def printReportLog(matchInfo,page=1):
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
    print ("Here are the list of commands available to you:")
    print ("Use 'w,a,s,d' and their diagonals 'q,e,z,c' to move the mech")
    print ("Type 'r' to see your team's unread reports, 'rep' will prompt you for page number for full the report log")
    print ("Type 'next' to switch to the next mech in you squad")
    matchInfo.advTurn = False

