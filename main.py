import gameClasses as C
import printHUD as ph
import printView as pv
import mechObjects as MO
import pilots as P
import inputs as pi
import random as r

game = True


playermech= C.Entity(MO.test,P.testpilot)
mech= C.Entity(MO.lancer,P.testpilot2)
playerSquad = C.Squad("Player Squad",[playermech, mech],"Combat",playerControlled= True)
playerTeam = C.Team("Player Team",[playerSquad])

enemymech = C.Entity(MO.lancer,P.enemypilot)
enemymech2 = C.Entity(MO.test,P.enemypilot2)
enemySquad = C.Squad("Enemy Squad",[enemymech,enemymech2],"Combat")
enemies = C.Team("Enemy Team",[enemySquad])

matchInfo = C.MatchInfo( 100, 19, [enemies, playerTeam], "")

while game is True:
    #TODO prematch UI/campaign management/mission sets/ mech and squad creation
    match = True
    matchInfo.mapInit()

    for team in  matchInfo.teamList: 
        for squad in team.squadsList:
            if squad.playerControlled == True:
                matchInfo.playerSquad = squad
            for mech in squad.mechList:
                matchInfo.entities.append(mech)
            squad.spawnSquad(matchInfo.map,[r.randint(1,len(matchInfo.map)-1), r.randint(1,len(matchInfo.map)-1)])

    while match is True:
        round = True
        for team in  matchInfo.teamList:
            for squad in team.squadsList: #apply sensor data for all objects
                if squad.playerControlled != True:
                    squad.roundRefresh(matchInfo)
        matchInfo.pov = matchInfo.playerSquad.mechList[0] #end on player squad as they go first
        matchInfo.pov.squad.roundRefresh(matchInfo)
        while round == True:
            
            action = False
            while action is False:
                
                matchInfo.pov.getVisuals(matchInfo)
                ph.displayHUD(matchInfo)
                pv.printPOV(matchInfo, matchInfo.pov.pos[0], matchInfo.pov.pos[1])
                matchInfo.advTurn = False
                pi.recieveInput(matchInfo)
                while matchInfo.advTurn == False:
                    ph.displayHUD(matchInfo)
                    pv.printPOV(matchInfo, matchInfo.pov.pos[0], matchInfo.pov.pos[1])
                    pi.recieveInput(matchInfo)

    print("Game Over")