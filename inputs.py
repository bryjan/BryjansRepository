#TODO move movement under the entity object and make sure movement costs are applied correctly
import gameClasses as c

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
            return nextMech(matchInfo)
        case "q" | "w" | "e" | "a" | "s" | "d" | "z" | "c":
            return moveMech(matchInfo, playerInput)
        case "r":
            return printUnreads(matchInfo)
        case _:
            print("Input not recognized. Try again.")
            return
    
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

def helpCommand(matchInfo):
    print ("Here are the list of commands available to you:")
    print ("Use 'w,a,s,d' and their diagonals 'q,e,z,c' to move the mech")
    print ("Type 'r' to see your team's unread reports, 'rep' will prompt you for page number for full the report log")
    print ("Type 'next' to switch to the next mech in you squad")
    matchInfo.advTurn = False
    
def moveMech(matchInfo, input):
    map = matchInfo.map
    mech = matchInfo.pov
    targetCell = matchInfo.map[mech.pos[0]][mech.pos[1]] #just to initialize to avoid error

    if mech.ap == 0 or mech.mp == 0 or mech.energy == 0:
        print("You don't have the ability to move anymore this turn.")
        matchInfo.advTurn = False
        return
    
    match input:

        case "q":
            targetPos = [mech.pos[0]-1,mech.pos[1]+1]
            targetCell = map[targetPos[1]][targetPos[0]]
            moveCost = targetCell.terrain.moveCost[mech.size]

        case "w":
            targetPos = [mech.pos[0],mech.pos[1]+1]
            targetCell = map[targetPos[1]][targetPos[0]]
            moveCost = targetCell.terrain.moveCost[mech.size]

        case "e":
            targetPos = [mech.pos[0]+1,mech.pos[1]+1]
            targetCell = map[targetPos[1]][targetPos[0]]
            moveCost = targetCell.terrain.moveCost[mech.size]

        case "a":
            targetPos = [mech.pos[0]-1,mech.pos[1]]
            targetCell = map[targetPos[1]][targetPos[0]]
            moveCost = targetCell.terrain.moveCost[mech.size]

        case "s":
            targetPos = [mech.pos[0],mech.pos[1]-1]
            targetCell = map[targetPos[1]][targetPos[0]]
            moveCost = targetCell.terrain.moveCost[mech.size]

        case "d":
            targetPos = [mech.pos[0]+1,mech.pos[1]]
            targetCell = map[targetPos[1]][targetPos[0]]
            moveCost = targetCell.terrain.moveCost[mech.size]

        case "z":
            targetPos = [mech.pos[0]-1,mech.pos[1]-1]
            targetCell = map[targetPos[1]][targetPos[0]]
            moveCost = targetCell.terrain.moveCost[mech.size]

        case "c":
            targetPos = [mech.pos[0]+1,mech.pos[1]-1]
            targetCell = map[targetPos[1]][targetPos[0]]
            moveCost = targetCell.terrain.moveCost[mech.size]
        case _:
            print("Not a valid movement input.")
            return

    #checks for viability

    if targetCell.terrain.passable == False: #checks if it's passable terrain
        print("This cell's terrain is impassable.")
        return
    
    for obj in matchInfo.entities: #checks for other objects
        if obj.pos == targetPos:
            print("Something is in your way.")
            return
        
    if mech.energy < moveCost: #checks energy cost
        name = targetCell.terrain.name
        print(f"You don't have enough energy to travel over {name}, you need {moveCost}.")
        return
        
    if mech.flying == True: #checks for if their is enough energy to fly
        flyMoveCost = mech.size
        if mech.energy < flyMoveCost:
            print(f"You need {moveCost} Energy to fly.")
            return

    if targetCell.terrain.requireFloat == True and mech.float == False and mech.flying == False: #checks for float conditions then flying
        print("Your mech can't travel over water.")
        return
    
    mech.energy = int(mech.energy - moveCost)
    mech.ap -= 1
    mech.mp = int(mech.mp-moveCost) #applies costs
    mech.pos = list(targetPos)
    mech.speed += 1
    matchInfo.advTurn = True
    
        

