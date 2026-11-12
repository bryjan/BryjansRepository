import termcolor

def displayHUD(matchInfo):
    """Render the current mech's resources and movement state."""
    mech = matchInfo.pov
    condPercent= round(mech.mechClass.condition)

    print()
    criticalReports(matchInfo)
    print (mech.pilot.name + " | Coordinates: " + str(mech.pos) +" | Status: " + str(condPercent) + "% | Current Tile: ", end =" ") 
    matchInfo.map[mech.pos[1]][mech.pos[0]].terrain.displayTerrain()
    print()
    radarStatus = "ON" if mech.radarOn else "OFF"
    print("AP: "+ str(mech.ap) + "/" + str(mech.mechClass.apMax) + " | " + "MP: " + str(mech.mp)+"/"+str(mech.mechClass.mpMax) + " | " + "Energy: " + str(mech.energy) + "/" + str(mech.mechClass.energyMax) + " Regen:" + str(mech.mechClass.energyGen) + " Speed:" + str(mech.speed) + " Radar:" + radarStatus)
    print()
    
def report(matchInfo, mech, message, teamReport = False, critical = False): #TODO add messages to a report log
    """Format and store a report for a mech or its entire team."""
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
    """Print critical reports stored on the match state."""
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
