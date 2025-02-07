import termcolor

def displayHUD(matchInfo):
    mech = matchInfo.pov
    hpRatio = mech.mechClass.condition
    hpPercent= round(hpRatio*100)

    print()
    criticalReports(matchInfo)
    print (mech.pilot.name + " | Coordinates: " + str(mech.pos) +" | Status: " + str(hpPercent) + "% | Current Tile: ", end =" ") 
    matchInfo.map[mech.pos[1]][mech.pos[0]].terrain.displayTerrain()
    print()
    print("AP: "+ str(mech.ap) + "/" + str(mech.mechClass.apMax) + " | " + "MP: " + str(mech.mp)+"/"+str(mech.mechClass.mpMax) + " | " + "Energy: " + str(mech.energy) + "/" + str(mech.mechClass.energyMax) + " Regen:" + str(mech.mechClass.energyGen))
    print()
    
def report(matchInfo, mech, message, teamReport = False, critical = False): #TODO add messages to a report log
    matchRound = matchInfo.matchRound
    critMessage = ""
    if critical == True:
        critMessage = "CRITICAL MESSAGE! | "
    report = f"{critMessage}Round: {matchRound}  |  {mech.pilot.name}:  {message}"
    for rep in mech.squad.reportLog:
        if rep[0] == report:
            return
    mech.squad.reportLog.insert(0,[report, critical, False]) #[report, critical?, already display?]
    if teamReport == True:
        mech.squad.reportLog.insert(0,[report, critical, False])

def criticalReports(matchstats):
    mech = matchstats.pov
    matchstats.advTurn = False
    pageSize = 40
    numrep = 0
    for rep in mech.squad.reportLog:
        if rep[2] == False and rep[1] == True:
            print (rep[0])
            rep[2] = True
            
        numrep+=1
        if numrep > pageSize:
            return
    print()