
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

