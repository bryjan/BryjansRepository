import math
import functions as f
import copy
import random
from termcolor import colored, cprint #print(colored(string, color as string),attrs=[bold,dark,underline,blink,reverse,concealed],end='')

class MatchInfo:
    def __init__(self, mapSize, windowSize, teams, mapParams):
        
        self.mapSize = mapSize
        self.windowSize = windowSize
        self.teamList = teams #team0 are nuetral entities
        self.playerSquad = ""
        self.entities = []
        self.abandonedMechs = []
        self.destroyedMechs = []
        self.matchRound = 0
        self.pov = ""
        self.mapParamsList = mapParams
        self.map = []
        self.advTurn = False #did POV take a turn ending action (ap costing). reading reports dont advance the turn, moving would, ect.

        self.blank = TerrainType("blank", " ", "black", size= 0, moveCostBySize = [], visualAbsorbtion = 9999, radarAbsorbtion = 9999, fireproof = True, passable = False)
        self.border = TerrainType("border", "X", "white", size= 0, moveCostBySize = [9999,9999,9999,9999,9999,9999,9999], visualAbsorbtion = 1, radarAbsorbtion =1, radarSig = 1, fireproof = True, passable = False)
        self.desert = TerrainType("desert", "~", "yellow", size= 0, moveCostBySize = [1,2,3,2,1,1,1], visualAbsorbtion = 2, radarAbsorbtion = 1, radarSig = 9999, fireproof = True)
        self.plains = TerrainType("plains", "_", "light_green", size= 0, moveCostBySize = [1,1,1,1,1,1,1], visualAbsorbtion = 1, radarAbsorbtion = 1,radarSig = 9999)
        self.forest = TerrainType("forest", "t", "green", size= 3, moveCostBySize = [1,1,2,4,3,1,1], visualAbsorbtion = 6, radarAbsorbtion = 15, radarSig = 100)
        self.suburb = TerrainType("suburbs", "H", "light_grey", size= 3, moveCostBySize = [1,1,1,5,4,2,1], visualAbsorbtion = 20, radarAbsorbtion = 40, radarSig = 80)
        self.road = TerrainType("road", "=", "dark_grey", size= 0, moveCostBySize = [0,0,0,0,0,0,0], visualAbsorbtion = 1, radarAbsorbtion = 0, radarSig = 9999, requireFloat = False, fireproof = True)

    def spawnEntities(self):
        pass #TODO

    def nextSquadTurn(self):
        teamIndex = self.teamList.index(self.pov.team)
        squadIndex = self.pov.team.squadsList.index(self.pov.squad)
    
        if squadIndex + 1 > len(self.pov.team.squadsList) - 1:
            self.clearVisuals()
            nextSquadIndex = 0
            nextTeamIndex = teamIndex + 1

            if teamIndex + 1 > len(self.teamList) - 1: #start of new round
                self.matchRound += 1
                #TODO refresh round stats
                nextTeamIndex = 0
            
        self.pov = self.teamList[nextTeamIndex].squadsList[nextSquadIndex].mechList[0]

        for mech in self.pov.squad.mechList:
            if mech.cockpit.status == 0:
                self.destoryedMechs.append(mech)
                mech.squad.mechlist.remove(mech)
                self.entities.remove(mech)
        self.pov.squad.roundRefresh(self)
        self.advTurn = True

    def nextMechinTeam(self):
        nextMechIndex = self.pov.squad.mechList.index(self.pov) + 1
    
        if nextMechIndex > len(self.pov.squad.mechList)-1:
            nextMechIndex = 0
    
        self.pov = self.pov.squad.mechList[nextMechIndex]
        self.advTurn = False

    def clearVisuals(self):
        for y in self.map:
            for x in y:
                x.canSee = False
                x.visPower = 0
                x.radarReturn = False
                x.radarPower = 0

    
    
    def explosion(self, location, radius, size, damage): #spawns explosions. for rockets/artillery
        
        pos = location #[x , y]
        radius = radius #radius of explosion
        size = size
        dmg = damage

        #calc effected entities
        affectedEntities = []
        for entity in self.entities:
            if math.dist(pos, entity.pos) <= radius:
                affectedEntities.append(entity)

        #calc affected limbs by size difference between explosion and mech
        calcList = []
        affectedLimbs = 3
        for entity in affectedEntities:
            sizeDif = size - entity.size
            calcList.append(entity, affectedLimbs + sizeDif)

        #calc dmg
        for entry in calcList:
            while entry[1] > 0:
                entry[0].damage(self, dmg, "explosion", armorDamage = 1 + sizeDif)


        #TODO chance to start fire

    def calcLine(self, point1, point2):

        x1, y1 = point1
        x2, y2 = point2

        slope = (y1 - y2) / (x1 - x2)
        yIntercept = y1 - (slope * x1)

        return [slope, yIntercept]

    def ListInterceptingSquares(self, point1, point2):

        interceptingCells = []
        
        if point1[0] == point2[0]:

            for i in range(min(point1[1], point2[1]), max(point1[1], point2[1]) + 1):
                interceptingCells.append(self.map[i][point1[0]])
    
            return interceptingCells

        if point1[1] == point2[1]:

            for i in range(min(point1[0], point2[0]), max(point1[0], point2[0]) + 1):
                interceptingCells.append(self.map[point1[1]][i])

            return interceptingCells

        slope, intercept = self.calcLine(point1, point2)

        if abs(slope) <= 1:
            for i in range(min(point1[0], point2[0]), max(point1[0], point2[0]) + 1):
                y = round((slope * i) + intercept)
                interceptingCells.append(self.map[i][y])
            return interceptingCells

        elif abs(slope) > 1:
            for i in range(min(point1[1], point2[1]), max(point1[1], point2[1]) + 1):
                x = round((i - intercept) / slope)
                interceptingCells.append(self.map[x][i])
            return interceptingCells


    def mapInit(self): # runs all map init functions
        self.mapinitPop()
        self.basicTileInit()
        self.redefineBorders()

    def mapinitPop(self): #populates map with a tile to start
        mapArray = []
        xRow = []
        y = 0
        while y <= self.mapSize-1:
            x = 0
            while x <= self.mapSize-1:
                if x == 0 or y == 0 or x == self.mapSize-1 or y == self.mapSize-1 :
                    xRow.append(Cell(self.border,[x,y])) #makes the cells at the edge border tiles
                else:
                    xRow.append(Cell(self.plains,[x,y]))
                x+=1
            mapArray.append(xRow)
            y+=1
            xRow=[]
        self.map = mapArray

        for y in self.map: #adds a reference to neighbors for every cell
            for cell in y:
                cell.refNeighbors(self.map)

    def basicTileInit(self):
        self.forest.basicTileGen(self.map,"Normal")
        self.desert.basicTileGen(self.map,"Light")
        self.randomRoadGen(self.map,"Normal")
        self.suburb.associationTileGen(self.map, "Normal", [self.road, self.suburb])

    def redefineBorders(self):
        for y in self.map:
            for x in y:
                if x == 0 or y == 0 or x == self.mapSize-1 or y == self.mapSize-1 :
                    x.terrain = self.border

    def createRoad(self, map, target1Pos, target2Pos): #makes a road between two points, with slight deviations

        activeCell = map[target1Pos[1]][target1Pos[0]]
        targetCell = map[target2Pos[1]][target2Pos[0]]
        targetCell.terrain = self.road
        activeCell.terrain = self.road

        while activeCell.pos != targetCell.pos and activeCell.pos[0] > 2 and activeCell.pos[0] < len(map)-2 and activeCell.pos[1] > 2 and activeCell.pos[1] < len(map)-2:
            activeCell.terrain = self.road
            activeCell = activeCell.refClosestNeighborTo(targetCell.pos)

        if math.dist(activeCell.pos,targetCell.pos) < 2:
            activeCell.terrain = self.road
            activeCell = targetCell
            return

        if random.randint(1,9) == 1: #Randomly deviate by one tile
            activeCell = random.choice(activeCell.refPerpendicularNeigbors(targetCell.pos))

    def createStraightRoad(self, map, target1Pos, target2Pos): #makes a road between two points, with slight deviations
        
        roadList = self.ListInterceptingSquares(target1Pos, target2Pos)

        for cell in roadList:
            cell.terrain = self.road
        return
        
    def createHighway(self, map, target1Pos, target2Pos, AdjTarget1Pos = [], AdjTarget2Pos = []):
        
        target1Cell = map[target1Pos[1]][target1Pos[0]]
        target2Cell = map[target2Pos[1]][target2Pos[0]]

        if AdjTarget1Pos == [] and AdjTarget2Pos == []:
            nextStartPos = random.choice(target1Cell.refPerpendicularNeigbors(target2Pos)).pos #picking a perpendicular neighbor to make parallel road
            nextEndPos = target2Cell.nList[target1Cell.nList.index(map[nextStartPos[1]][nextStartPos[0]])].pos #matching neighbor
        else:
            nextStartPos = AdjTarget1Pos
            nextEndPos = AdjTarget2Pos

        self.createStraightRoad(map,target1Pos,target2Pos)
        self.createStraightRoad(map,nextStartPos,nextEndPos)

    def randomRoadGen(self, map, density): #["None","Light","Normal","Thick"]
        
        densityList=["None","Light","Normal","Thick"]
        if density not in densityList:
            print(str(density) + "is not a valid density setting. Please use 'None','Light','Normal',and 'Thick'")
            return
        else:
            densityMult= densityList.index(density)
            seedingChance = densityMult #roads per 20 tile radius or n in 4000
            totalTiles = len(map)*len(map)
            roadsPerSeed = round(totalTiles/4000,0) #~3 for a 100x100 map
            expectedRoads = roadsPerSeed * seedingChance
            roads=0

            #constuct Highways = densityMult
            highways=0
            while highways < densityMult:
                highways+=1
                roads+=1
            
                startcell = map[random.randint(2,len(map)-2)][random.randint(2,len(map)-2)]
                endcell = map[random.randint(2,len(map)-2)][random.randint(2,len(map)-2)]

                while math.dist(startcell.pos,endcell.pos) < len(map): #making sure the Highway is actually long
                    startcell = map[random.randint(2,len(map)-2)][random.randint(2,len(map)-2)]
                    endcell = map[random.randint(2,len(map)-2)][random.randint(2,len(map)-2)]
            
                self.createHighway(map, startcell.pos, endcell.pos)

            while roads < expectedRoads:
                roads+=1
                startcell = map[random.randint(2,len(map)-2)][random.randint(2,len(map)-2)]
                endcell = map[random.randint(2,len(map)-2)][random.randint(2,len(map)-2)]

                while math.dist(startcell.pos,endcell.pos) < len(map): #making sure the road is actually long
                    startcell = map[random.randint(2,len(map)-2)][random.randint(2,len(map)-2)]
                    endcell = map[random.randint(2,len(map)-2)][random.randint(2,len(map)-2)]
                
                self.createRoad(map, startcell.pos, endcell.pos)



#key descriptions in dictionary
class TerrainType:
    def __init__(self, name, symbol, color,size= 0, moveCostBySize=[], visualAbsorbtion = 0, radarAbsorbtion = 0, radarSig = 0, requireFloat = False, fireproof = False, passable = True, symbolHighlight = "", symbolAttribute = []):
        self.name = name
        self.symbol = symbol
        self.color = color
        self.size = size
        self.moveCost = moveCostBySize
        self.visAbsorb = visualAbsorbtion
        self.radarAbsorb = radarAbsorbtion
        self.radarSig = radarSig
        self.requireFloat = requireFloat
        self.fireproof = fireproof
        self.symbolAttribute = symbolAttribute
        self.symbolHighlight = symbolHighlight
        self.passable = passable

    def basicTileGen(self, map, density): #["None","Light","Normal","Thick"]
        densityList = ["None","Light","Normal","Thick"]
        if density not in densityList:
            print(str(density) + "is not a valid density setting. Please use 'None','Light','Normal',and 'Thick'")
            return
        else:
            densityMult = densityList.index(density)
            seedingChance = 3 #out of 1000
            neighborConversionChance = 25 #out of 100
            for y in map[1 : len(map) - 1]:
                for cell in y[1:len(y)-1]: #to avoid flipping border tiles
                    if (random.randint(1, 1000) <= seedingChance * densityMult):
                        cell.terrain = self
            
            genLoops = densityMult

            i = 0
            while i < genLoops:
                i+=1
                changeQueue=[] #using a neighbors terrain to determine if you flip will cause a slant if you make changes during the loop
                for y in map[2:len(map)-2]:
                    for cell in y[2:len(y)-2]:
                        flipRoll = False
                        numTerrain = 0
                        for n in cell.nList:
                            if n.terrain == self:
                                flipRoll = True
                                numTerrain += 1
                        if flipRoll is True:
                            if (random.randint(1 , 100) + numTerrain < neighborConversionChance):
                                changeQueue.append(cell)
                        for cell in changeQueue:
                            cell.terrain = self
                changeQueue=[]

    def associationTileGen(self, map, density, associatedTerrainList): # Places a terrain tile next to an associated tile
        densityList = ["None","Light","Normal","Thick"]
        if density not in densityList:
            print(str(density) + "is not a valid density setting. Please use 'None','Light','Normal', and 'Thick'")
            return
        else:
            densityMult = densityList.index(density)
            neighborConversionChance = 5 #out of 100
            genLoops = densityMult

            i = 0
            while i < genLoops:
                i+=1
                changeQueue=[] #using a neighbors terrain to determine if you flip will cause a slant if you make changes during the loop
                for y in map[2:len(map)-2]:
                    for cell in y[2:len(y)-2]:
                        flipRoll = False
                        numTerrain = 0
                        for n in cell.nList:
                            if n.terrain in associatedTerrainList:
                                flipRoll = True
                                numTerrain += 1 # more neighbors of associated type = greater chance of flipping. makes tighter groups
                        if flipRoll is True and cell.terrain not in associatedTerrainList:
                            if (random.randint(1 , 100) + numTerrain < neighborConversionChance):
                                changeQueue.append(cell)
                        for cell in changeQueue:
                            cell.terrain = self
                changeQueue=[]
          
    def displayTerrain(self):
        if self.symbolAttribute != [] and self.symbolHighlight != "":
            return cprint(self.symbol,self.color,self.symbolHighlight,attrs=[self.symbolAttribute], end = " ")
        
        elif self.symbolHighlight != "":
            return cprint(self.symbol,self.color,self.symbolHighlight,end = " ")
        
        elif self.symbolAttribute != []:
            return cprint(self.symbol,self.color,attrs=[self.symbolAttribute], end = " ")

        else:
            return print(colored(self.symbol,self.color), end = " ")


class Cell:
    def __init__ (self, terrainType, xyPosition):
        self.terrain = terrainType
        self.pos = xyPosition
        self.nList = [] #list of neighbor positions for calculations

        self.onFire = 0
        self.onSmoke = 0
        self.onChaff = 0
        self.EnergyShieldValue = 0

        self.radarPower = 0
        self.visualPower = 0

        self.canSee = False
        self.radarReturn = False
        
    def refNeighbors(self,map): #gets a list of neighbor cells to refernce for calculations
        self.nList=[]

        if (self.pos[1] + 1 <= len(map)-1) and (self.pos[0] - 1 >= 0):
            self.nList.append(map[self.pos[1] + 1][self.pos[0] - 1])  # north west
        if self.pos[1] + 1 <= len(map)-1:   
            self.nList.append(map[self.pos[1] + 1][self.pos[0]])  # north
        if (self.pos[1] + 1 <= len(map)-1) and (self.pos[0] + 1 <= len(map)-1):
            self.nList.append(map[self.pos[1] + 1][self.pos[0] + 1])  # north east
        if self.pos[0] - 1 >= 0:
            self.nList.append(map[self.pos[1]][self.pos[0] - 1])  # west
        if self.pos[0] + 1 <= len(map)-1:
            self.nList.append(map[self.pos[1]][self.pos[0] + 1])  # east
        if (self.pos[1] - 1 >= 0)  and (self.pos[0] - 1 >= 0):
            self.nList.append(map[self.pos[1] - 1][self.pos[0] - 1])  # south west
        if self.pos[1] - 1 >= 0:
            self.nList.append(map[self.pos[1] - 1][self.pos[0]])  # south
        if (self.pos[1] - 1 >= 0) and (self.pos[0] + 1 <= len(map)-1):
            self.nList.append(map[self.pos[1] - 1][self.pos[0] + 1])  # south east
    
    def refClosestNeighborTo(self,targetPos): #returns neighbor cell's position closest to target
        
        lowestDistance = 9999999
        closestNeighbor = ""
        
        for n in self.nList:
            if (math.dist(n.pos,targetPos) < lowestDistance):
                closestNeighbor = n
                lowestDistance = math.dist(n.pos,targetPos)

        if type(closestNeighbor) == type(""):
            print(str(self.pos) + "closestNeigbor returned string")
            return
        return closestNeighbor
    
    def refFurthestNeighborTo(self,targetPos): #returns neighbor cell's position closest to target
        
        highestDistance = -9999
        furthestNeighbor = ""

        for n in self.nList:
            if math.dist(n.pos,targetPos) > highestDistance:
                furthestNeighbor = n
                highestDistance = math.dist(n.pos,targetPos)

        if type(furthestNeighbor) == type(""):
            print(str(self.pos) + "furthest neighbor returned string")
            return
        return furthestNeighbor
    
    def refPerpendicularNeigbors(self,targetPos):#returns a list
         neighbors=[]
         dists=[]
         for n in self.nList:
             dists.append(math.dist(n.pos,targetPos))
             neighbors.append(n)
             
         i=0
         while i < 3:
             i+=1
             neighbors.pop(dists.index(max(dists)))
             dists.pop(dists.index(max(dists)))
             neighbors.pop(dists.index(min(dists)))
             dists.pop(dists.index(min(dists)))

         return neighbors
        

    def displayCell(self, matchInfo): #TODO what will the cell print on map. smoke and fire affects will be displayed through here too
        
        for entity in matchInfo.entities:
            if entity.pos == self.pos:
                entity.displayObject()
                return
        else:
            self.terrain.displayTerrain()
            return

    def displayRadarReturn(self, matchInfo):

        for entity in matchInfo.entities:
            if entity.pos == self.pos and self.radarPower >= (entity.radarSig * 2):
                entity.displayObject()
                return
            if entity.pos == self.pos and self.radarPower >= entity.radarSig:
                print(colored("?", "white"), end=" ")
                return
        
        if self.radarReturn == True and self.radarPower >= self.terrain.radarSig:
            print(colored("?", "white"), end=" ")
            return
        else:
            print(" ", end = " ")
            return
    
    def roundRefresh(self): #TODO reset stats that refresh every round ex)radar and visual strength, radar sources then counting down cell effects
        pass

#TODO add ejection mechanic and entity from sqaud, team, and entities list. but track pilot and mech condition for post-battle recovery
class Entity: #a character on the map
    def __init__(self, mechClass, pilot):
        self.mechClass = copy.deepcopy(mechClass)
        self.mechClass.mech = self

        self.pilot = copy.deepcopy(pilot)
        for limb in self.mechClass.limbList:
            limb.mech = self
        #inserts pilot into mech's Helm
        cockpit = Cockpit("Pilot", "multi ap", 3, ["0", ".75", "1"], self.pilot, False)
        self.mechClass.helm.modsList.append(cockpit)

        self.name = self.pilot.name
        self.squad = ""
        self.team = ""

        self.pos = [0,0] #[x,y]
        self.size = self.mechClass.size
        self.sizeStr = self.mechClass.sizeStr
        self.speed = 0 #tiles moved this turn
        self.ap = int(self.mechClass.apMax)
        self.mp = int(self.mechClass.mpMax)
        self.energy = int(self.mechClass.energyMax)
        self.visPower = self.mechClass.visPower
        self.radarPower = self.radarPower = self.mechClass.radarPower / (1 + (self.speed * .25 ))
        self.radarOn = True

        self.turnStartPos = list(self.pos)
        self.flying = self.mechClass.initFlying
        self.baseRadarSig = self.mechClass.radarSig
        self.radarSig = (self.baseRadarSig / (1 + (self.speed * .2 )))

        self.visibleCells = []
        self.radarIDlist = [] #items in form of [location, size, direction, speed, objectSymbol, ObjectName] level of radar power reveals more info

        #ai flags
        self.travelSpeed = max(self.mechClass.apMax, self.mechClass.mpMax)
        self.needrest = False
  

    def __repr__(self):
        return self.pilot.name
    
    def roundRefresh(self, matchInfo):

        #basic stats
        self.turnStartPos = list(self.pos)
        self.speed = 0

        self.ap = int(self.mechClass.apMax)
        self.mp = int(self.mechClass.mpMax)

        self.energy += self.mechClass.energyGen
        if self.energy > self.mechClass.energyMax:
            self.energy = int(self.mechClass.energyMax)

        #get visuals
        self.getVisuals(matchInfo)

        #ai flags calc
        if self.ap == 0 or self.mp == 0 or self.energy <= (self.mechClass.energyMax * .4):
            self.needrest = True


    
    def moveMech(self, matchInfo, input):
        map = matchInfo.map
        targetCell = matchInfo.map[self.pos[0]][self.pos[1]] #just to initialize to avoid error

        if self.ap == 0 or self.mp == 0 or self.energy == 0:
            print("You don't have the ability to move anymore this turn.")
            matchInfo.advTurn = False
            return
    
        match input:

            case "q":
                targetPos = [self.pos[0]-1, self.pos[1]+1]
                targetCell = map[targetPos[1]][targetPos[0]]
                moveCost = targetCell.terrain.moveCost[self.size]

            case "w":
                targetPos = [self.pos[0], self.pos[1]+1]
                targetCell = map[targetPos[1]][targetPos[0]]
                moveCost = targetCell.terrain.moveCost[self.size]

            case "e":
                targetPos = [self.pos[0]+1, self.pos[1]+1]
                targetCell = map[targetPos[1]][targetPos[0]]
                moveCost = targetCell.terrain.moveCost[self.size]

            case "a":
                targetPos = [self.pos[0]-1, self.pos[1]]
                targetCell = map[targetPos[1]][targetPos[0]]
                moveCost = targetCell.terrain.moveCost[self.size]

            case "s":
                targetPos = [self.pos[0], self.pos[1]-1]
                targetCell = map[targetPos[1]][targetPos[0]]
                moveCost = targetCell.terrain.moveCost[self.size]

            case "d":
                targetPos = [self.pos[0] + 1, self.pos[1]]
                targetCell = map[targetPos[1]][targetPos[0]]
                moveCost = targetCell.terrain.moveCost[self.size]

            case "z":
                targetPos = [self.pos[0] - 1, self.pos[1]-1]
                targetCell = map[targetPos[1]][targetPos[0]]
                moveCost = targetCell.terrain.moveCost[self.size]

            case "c":
                targetPos = [self.pos[0] + 1, self.pos[1]-1]
                targetCell = map[targetPos[1]][targetPos[0]]
                moveCost = targetCell.terrain.moveCost[self.size]

            case _:
                print("Not a valid movement input.")
                return

        #checks for viability
        if moveCost > self.energy:
            print("Not enough energy to pass over this terrain.")

        if targetCell.terrain.passable == False: #checks if it's passable terrain
            print("This cell's terrain is impassable.")
            return
    
        for obj in matchInfo.entities: #checks for other objects
            if obj.pos == targetPos:
                print("Something is in your way.")
                return
        
        if self.energy < moveCost: #checks energy cost
            name = targetCell.terrain.name
            print(f"You don't have enough energy to travel over {name}, you need {moveCost}.")
            return
        
        if self.flying == True: #checks for if their is enough energy to fly
            flyMoveCost = self.size
            if self.energy < flyMoveCost:
                print(f"You need {moveCost} Energy to fly.")
                return

        if targetCell.terrain.requireFloat == True and self.float == False and self.flying == False: #checks for float conditions then flying
            print("Your mech can't travel over water.")
            return
    
        self.energy = int(self.energy - moveCost) #applies costs
        self.ap -= 1
        self.mp = int(self.mp - 1) 
        self.pos = list(targetPos)
        self.speed += 1
        matchInfo.advTurn = True
    
    def getVis(self, matchInfo):
        startingCell = matchInfo.map[self.pos[1]][self.pos[0]]
        startingCell.canSee = True

        for y in matchInfo.map:
            for tile in y:
                tile.visPower = 0

        startingCell.visPower = int(self.visPower + startingCell.terrain.visAbsorb)
    
        calcList = [] #cells queued to be calced
        dontCalcList= [startingCell] #cells exempt from calcs
        if startingCell not in self.visibleCells:
            self.visibleCells.append(startingCell)
    
        for n in startingCell.nList:
            dontCalcList.append(n)
            if n.pos[0] > 0 and n.pos[0] < len(matchInfo.map) and n.pos[1] > 0 and n.pos[1] < len(matchInfo.map):
                calcList.append(n)
        
        for cell in calcList:
            dontCalcList.append(cell)
            closestNeighbor = cell.refClosestNeighborTo(startingCell.pos)
            visualLoss = int(closestNeighbor.terrain.visAbsorb) + round(math.dist(startingCell.pos,cell.pos),0)
            cell.visPower = int(closestNeighbor.visPower) - visualLoss
        
            if cell.visPower < 0:
                cell.visPower = 0

            if cell.visPower > 0:
                cell.canSee = True
                for n in cell.nList:
                    if (n not in dontCalcList):
                        calcList.append(n)
                        dontCalcList.append(n)

    def getRadar(self, matchInfo):
        map = matchInfo.map
        startingCell = map[self.pos[1]][self.pos[0]]
        self.radarPower = self.mechClass.radarPower / (1 + (self.speed * .25 ))
        if self.radarPower <= 0 or self.radarOn == False: #checks if entity has radar.
            return

        startingCell.radarPower = int(self.radarPower)
        self.radarIDlist.append(startingCell)
        startingCell.radarReturn = True

        calcList = [] #cells queued to be calced
        dontCalcList = [startingCell] #cells exempt from calcs
    
        for n in startingCell.nList:
            calcList.append(n)
        
        for cell in calcList:
            if cell not in dontCalcList:
                #print("calcd: " + str(cell.pos) + " | prevPower: " + str(cell.radarPower), end = " newPower:") #test
                dontCalcList.append(cell)
                closestNeighbor = cell.refClosestNeighborTo(startingCell.pos)
                radarLoss = int(closestNeighbor.terrain.radarAbsorb) + round(math.dist(startingCell.pos, cell.pos))
                cell.radarPower = int(closestNeighbor.radarPower) - radarLoss
                #print(cell.radarPower)#test

                if cell.radarPower < 0:
                    cell.radarPower = 0

                if cell.radarPower > 0:
                    cell.radarReturn = True
                    for n in cell.nList:
                        if (n not in dontCalcList):
                            calcList.append(n)

        for obj in matchInfo.entities: #passive radar and radar ID reports
            if obj.mechClass.passiveRadar == True and map[obj.pos[1]][obj.pos[0]].radarPower >= 25:
                if obj.team != self.team:
                    obj.passiveRadarDetect(matchInfo, self)
            if map[obj.pos[1]][obj.pos[0]].radarPower >= (obj.radarSig / (1 + (self.speed * .2 ))):
                if obj.team != self.team:
                    self.radarReport(matchInfo,map[obj.pos[1]][obj.pos[0]].radarPower, obj)

    def passiveRadarDetect(self, matchInfo, emittor):
        map = matchInfo.map
        repCritical = False
        emittorCell = map[emittor.pos[1]][emittor.pos[0]]
        direction = f.neswDirection(self.pos, emittorCell.pos)

        if self.team.name == emittor.team.name:
            return
        if map[self.pos[1]][self.pos[0]].radarPower < 50:
            return
        if self.mechClass.passiveRadar == False:
            return
        if self.entity.speed > 1:
            return 
    
        strength = map[self.pos[1]][self.pos[0]].radarPower

        if strength >= self.radarSig * 2:
            status = "identified"
            repCritical = True
        elif strength >= self.radarSig:
            status = "noticable"
            repCritical = True
        else:
            status = "undetected"

        return self.report(matchInfo,"Getting pinged from the " + direction + ". At " + str(strength) + " strength, I'm " + status + ".", critical = repCritical)
    
    def radarReport(self, matchInfo, radarPower, target):

        if radarPower < target.radarSig:
            return
    
        targetName = f""
        speed = f""
        moveDirection = f""
        size = "Unkown"

        if target.speed == 0:
            moveDirection = f", not moving"
        else:
            moveDir = f.neswDirection(target.turnStartPos, target.pos)
            moveDirection = f", moving {moveDir}"

        if radarPower >= target.radarSig * 2:
            targetName = f" Identified as {target.mechClass.name},"
            speed = f" Moving at {target.speed} units a turn."
    
        if radarPower >= target.radarSig * 1.5:
            size = target.sizeStr.capitalize()
            if target.speed == 0:
                moveDirection = f", not moving"
            
        message = f"{size} sized object detected on radar!{targetName} At {target.pos}{moveDirection}.{speed}" #constructing message
    
        self.report(matchInfo, message, critical = True)
    
    def getVisuals(self, matchInfo):
        self.getVis(matchInfo)
        self.getRadar(matchInfo)


    def report(self, matchInfo, message, teamReport = False, critical = False): #TODO add messages to a report log
        matchRound = matchInfo.matchRound
        critMessage = ""
        if critical == True:
            critMessage = "CRITICAL MESSAGE!| "
        report = f"{critMessage}Round: {matchRound} |  {self.pilot.name}: {message}"
        for rep in self.squad.reportLog:
            if rep[0] == report:
                return
        self.squad.reportLog.insert(0,[report, critical, False]) #[report, critical?, already display?]
        if teamReport == True:
            self.team.reportLog.insert(0,[report, critical, False])

    def criticalReports(matchInfo):
        mech = matchInfo.pov
        matchInfo.pov= False
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

    def displayObject(self):
        
        return print(colored(self.mechClass.symbol,self.mechClass.color), end = " ")


class Pilot: #TODO add pilot levels, skills, certs
    def __init__(self, name):
         self.name = name


class MechClass: #a constructed mech not a npc or player
    def __init__(self, name, symbol, color, mechHull, mechHelm, mechLeg, limblist = [], description = ""):

        #basic details
        self.name = name
        self.symbol = symbol
        self.color = color
        self.mech = ""
    
        #limb objects
        self.hull = copy.deepcopy(mechHull)
        self.helm = copy.deepcopy(mechHelm)
        self.legs = copy.deepcopy(mechLeg)
        #limbs roughly organized by height off ground
        self.limbList = [self.legs, self.hull]
        self.gunList = []
        for limb in limblist:
            self.limbList.append(copy.deepcopy(limb))
        self.limbList.append(self.helm)

        for limb in self.limbList:
            limb.mechClass = self
            if limb.isGun == True:
                self.gunList.append(limb)
        if len(self.gunList) == 1:
            self.gunList[0].defaultGun = True

        #initialize limb passed stats
        self.limbsConditionList = []
        self.size = 0
        self.radarSig = 0
        self.apMax = 0
        self.mpMax = 0
        self.energyMax = 0
        self.energyGen = 0
        self.shareData = False
        self.visPower = 0
        self.radarPower = 0
        self.passiveRadar = False
        self.canfloat = False
        self.canFly = False
        self.initFlying = False

        self.passedStatsList = ["size","radarSig","apMax","mpMax","energyMax","energyGen","shareData","visPower","radarPower","passiveRadar","canFly","canFloat","initFlying"]

        self.statUpdate()

        self.condition = sum(self.limbsConditionList) / len(self.limbsConditionList) * 100
        self.sizeStrList = ["flat", "tiny", "small", "medium", "large", "huge", "titanic"]
        self.sizeStr = self.sizeStrList[self.size]

        self.desc = description

    def displayStats(self): #basic stats display for bug fixing. TODO redo to look nicer and adding descriptions for gameplay
        pass

    def statUpdate(self):
        #retrieve limb passed stats
         for limb in self.limbList:
            limb.updateModules()
            self.limbsConditionList.append(limb.limbCon)
            for stat in self.passedStatsList:
                if getattr(limb, stat, "No attribute of that Name") != "No attribute of that Name":
                    setattr(self, stat, getattr(limb, stat))


    def statReset(self): #TODO resets mech's stats to default, including its limbs and modules
        pass

    def roundRefresh(self): #TODO refreshes round based stats(AP,MP,moved)and adds round based resources ex.power from powerGen
        pass

        
class MechPart: # super class to mech limbs
    def __init__ (self, name, armor, hp, moduleList, desc = ""):

        self.desc = desc
        self.name = name
        self.mechClass = "" #will be assigned when attached to a mech
        self.isGun = False
        
        self.modsList = copy.deepcopy(moduleList)

        #limb stats
        self.baseArmor = armor
        self.bonusArmor = 0
        self.multiArmor = 1
        self.armor = (self.baseArmor * self.multiArmor) + self.bonusArmor
        self.startingArmor = int(self.armor)
        self.armorCon = self.armor / self.startingArmor
       
        self.baseHP = hp
        self.bonusHP = 0
        self.multiHP = 1
        self.hp = (self.baseHP * self.multiHP) + self.bonusHP
        self.startingHP = int(self.hp)
        self.hpCon = self.hp / self.startingHP

        self.limbCon = round((self.armorCon * .25) + (self.hpCon * .75), 2)
        self.updateModules()

    def updateModules(self):
        for m in self.modsList:
            if m.modType == 1: #skips modules that make no stat change
                i = 0
                while i < len(m.statNames):
                    if getattr(self, m.statNames[i], "x") == "x":
                        #print(m.name + " is incompatable with " + self.name)
                        #print(self.name + " has no " + m.statNames[i])
                        return
                    else:
                        setattr(self, m.statNames[i], m.statsArray[i][m.status]) 
                        #print("updated " + m.name + " " + m.statNames[i] + " to " + str(m.statsArray[i][m.status]))
                    i += 1
        self.updateStats()

    def updateStats(self):

        if getattr(self, "isGun", False) != False:
            self.updateWeaponStats()
        
        if getattr(self, "isLauncher", False) != False:
            self.updateLauncherStats()

        if getattr(self, "size", False) != False:
            self.updateHullStats()

        if getattr(self, "apMax", False) != False:
            self.updateHelmStats()

        if getattr(self, "mpMax", False) != False:
            self.updateLegStats()



    def damage(self, matchInfo, dmgAmount, damageSource, armorPiercing = False, armorDamage = 0, ):

        #no negative damage values
        dmg = dmgAmount
        if dmgAmount < 0:
            dmg = 0

        armorDmg = armorDamage
        if armorDamage < 0:
            armorDmg = 0
        
        #damage source string for damage report
        dmgSource = f"" + damageSource

        #damage calc
        if armorPiercing == False:
            dmg = dmg - self.armor
            if dmg < 0:
                return
        else:
            dmg = round(dmg - (self.armor / 4))
            if dmg < 0:
                return

        #applying damage
        self.hp -= dmg
        if self.hp < 0:
            self.hp = 0

        self.armor -= armorDmg
        if self.armor < 0:
            self.armor = 0

        #determining if a module was damaged / crit
        if random.randint(0, self.hp) + dmgAmount > self.hp + self.armor:
            self.critical(matchInfo)

        #updating limb's condition
        self.updateStats()
        self.armorCon = self.armor / self.startingArmor
        self.hpCon = self.hp / self.startingHP
        self.limbCon = round((self.armorCon * .25) + (self.hpCon * .75), 2)
        self.mechClass.limbsConditionList = []
        for limb in self.mechClass.limbList:
            self.mechClass.limbsConditionList.append(limb.limbCon)
        self.mechClass.condition = round(sum(self.mechClass.limbsConditionList) / len(self.mechClass.limbList) * 100)

        #reporting damage
        self.mech.report(matchInfo, "I was hit by a " + dmgSource + "!", teamReport = False, critical = False)

    def critical (self, matchInfo):
        #checking if there is modules to damage
        if len(self.modsList) == 0:
            return
        totalStatus = 0
        for mod in self.modsList:
            totalStatus += mod.status
        if totalStatus == 0:
            return

        #picking random module from limb
        dmgdMod = random.choice(self.modsList)
        while dmgdMod.status == 0:
            dmgdMod = random.choice(self.modsList)

        self.mech.report(matchInfo, dmgdMod.name + " was damaged!", teamReport = False, critical = False)
        dmgdMod.damage()
        self.mechClass.statUpdate()
            

class Legs(MechPart): #subclass mechpart
    def __init__ (self, name, armor, hp, moduleList, speed, float = False, fly = False, desc = ""): #this will initi the superclass the same sats
        super().__init__(name, armor, hp, moduleList, desc="")
        
        self.baseMP = speed
        self.bonusMP = 0
        self.multiMP = 1
        self.mpMax = (self.baseMP * self.multiMP) + self.bonusMP

        self.canFloat = float
        self.canFly = fly
        self.initFly = fly

    def updateLegStats(self):
        self.mpMax = int((self.baseMP * self.multiMP) + self.bonusMP)

class Hull(MechPart):
    def __init__ (self, name, armor, hp, moduleList, pwrCapacity, pwrGen, radarSig, size, desc = ""):
        super().__init__(name, armor, hp, moduleList, desc = "")
        
        self.size = size
        
        self.baseRadarSig = radarSig
        self.bonusRadarSig = 0
        self.multiRadarSig = 1
        self.radarSig = (self.baseRadarSig * self.multiRadarSig) + self.bonusRadarSig

        self.baseEnergy = pwrCapacity
        self.bonusEnergy = 0
        self.multiEnergy = 1
        self.energyMax = (self.baseRadarSig * self.multiEnergy) + self.bonusEnergy

        self.baseEnergyGen = pwrGen
        self.bonusEnergyGen = 0
        self.multiEnergyGen = 1
        self.energyGen = (self.baseEnergyGen * self.multiEnergyGen) + self.bonusEnergyGen

    def updateHullStats(self):
        self.radarSig = int((self.baseRadarSig * self.multiRadarSig) + self.bonusRadarSig)
        self.energyMax = int((self.baseRadarSig * self.multiEnergy) + self.bonusEnergy)
        self.energyGen = int((self.baseEnergyGen * self.multiEnergyGen) + self.bonusEnergyGen)


class Helm(MechPart):
    def __init__ (self, name, armor, hp, moduleList, ap, visualPower, radarPower, desc=""):
        super().__init__(name, armor, hp, moduleList, desc="")
        self.baseAP = ap
        self.bonusAP = 0
        self.multiAP = 1
        self.apMax = (self.baseAP * self.multiAP) + self.bonusAP

        self.baseVisPower = visualPower
        self.bonusVisPower = 0
        self.multiVisPower = 1
        self.visPower = (self.baseVisPower * self.multiVisPower) + self.bonusVisPower

        self.baseRadarPower = radarPower
        self.bonusRadarPower = 0
        self.multiRadarPower = 1
        self.radarPower = (self.baseRadarPower * self.multiRadarPower) + self.bonusRadarPower

        self.shareData = True
        self.passiveRadar = False

    def updateHelmStats(self):
        self.apMax = int((self.baseAP * self.multiAP) + self.bonusAP)
        self.visPower = int((self.baseVisPower * self.multiVisPower) + self.bonusVisPower)
        self.visPower = int((self.baseVisPower * self.multiVisPower) + self.bonusVisPower)


class WeaponLimb(MechPart):
    def __init__ (self, name, armor, hp, moduleList, damage, accuracy, soundRep, charges, projectileCount = 1, apCost = 1, energyCost = 0, speedPenalty = 8, armorPiercing = False, armorDamage = 0, desc = ""):
        super().__init__(name, armor, hp, moduleList, desc = "")
        
        self.desc = desc
        self.isGun = True
        self.defaultGun = False

        self.baseProjectileCount = projectileCount
        self.bonusProjectileCount = 0
        self.multiProjectileCount = 1
        self.projectileCount = (self.baseProjectileCount * self.multiProjectileCount) + self.bonusProjectileCount

        self.baseDmg = damage
        self.bonusDmg = 0
        self.multiDmg = 1
        self.dmg = (self.baseDmg * self.multiDmg) + self.bonusDmg


        self.baseAccuracy = accuracy #affected by visAbsorb of tiles, higher means more accuracy
        self.bonusAccuracy = 0
        self.multiAccuracy = 1
        self.accuracy = (self.baseAccuracy * self.multiAccuracy) + self.bonusAccuracy

        self.baseSoundReport = soundRep #the distance the weapon can be heard from
        self.bonusSoundReport = 0
        self.multiSoundReport = 1
        self.soundReport = (self.baseSoundReport * self.multiSoundReport) + self.bonusSoundReport

        self.maxCharges = charges
        self.charges = charges #amount of ammo carried

        self.apCost = apCost
        self.energyCost = energyCost

        self.speedPenalty = speedPenalty

        self.piercing = armorPiercing

        self.armorDamage = armorDamage

        self.accuracyPenalty = 1

    def updateWeaponStats(self):
        self.projectileCount = int((self.baseProjectileCount * self.multiProjectileCount) + self.bonusProjectileCount)
        self.accuracy = int((self.baseAccuracy * self.multiAccuracy) + self.bonusAccuracy)
        self.soundReport = int((self.baseSoundReport * self.multiSoundReport) + self.bonusSoundReport)

    def emitSound(self, matchInfo):
        for entity in matchInfo.entities:
            if math.dist(matchInfo.pov.pos, entity.pos) <= self.soundReport and entity not in matchInfo.pov.squad.mechList:
                entity.report(matchInfo, "I hear shots. Sounds like a " + self.name + "." , teamReport = False, critical = False)
    
    def shootAt(self, matchInfo, pos):

        #check if enough resources
        if self.charges - 1 < 0:
            print("Out of ammo!")
            return
        if matchInfo.pov.ap - self.apCost < 0:
            print("Out of action points!")
            return
        if matchInfo.pov.energy - self.energyCost < 0:
            print("Not enough energy to fire!")
            return

        self.charges -= 1
        matchInfo.pov.ap -= self.apCost
        matchInfo.pov.energy -= self.energyCost
        
        #enemies will report noise
        self.emitSound(matchInfo)

        #Calculates shot based on terrain between you and target, ignores the tile you're standing on and directly infront
        path = matchInfo.ListInterceptingSquares(matchInfo.pov.pos, pos)
        removeList = matchInfo.map[matchInfo.pov.pos[1]][matchInfo.pov.pos[0]].nList
        removeList.append(matchInfo.map[matchInfo.pov.pos[1]][matchInfo.pov.pos[0]])

        for cell in removeList:
            if cell in path:
                path.remove(cell)

        accuracyRequired = 0
        for n in path:
            accuracyRequired += n.terrain.visAbsorb

        i = 1
        while i <= self.projectileCount:
            i += 1
            shotDeviation = 1
            if matchInfo.pov.speed > 0:
                shotDeviation = 1 - ((random.randint(0, self.speedPenalty) * matchInfo.pov.speed ) / 100) #move speed inaccuracy penalty
            shotAccuracy = self.accuracy * shotDeviation
            shotAccuracy = self.accuracy * self.accuracyPenalty
            
            if shotAccuracy < accuracyRequired:
                print("Shot missed!")
            else:
                print("Shot hit!")
                for mech in matchInfo.entities:
                    if mech.pos == pos:
                        #TODO add system to target specific limbs or make add weight table of limb chance to be hit
                        random.choice(mech.mechClass.limbList).damage(matchInfo, self.dmg, self.name, armorPiercing = self.piercing, armorDamage = self.armorDamage)

        matchInfo.advTurn = True

    def printShortDesc(self):

        return f"[{self.name} | Charges:({self.charges}/{self.maxCharges}) AP Cost:{self.apCost} Energy Cost:{self.energyCost}]"


#clean up module system and make it work (not updating)
class Module: #supposed to be superclass but couldn't figure it out
    def __init__(self, name, attrNames, bonusType, statChangeList, desc = ""): #[destroyed bonus, damaged bonus, good bonus]
        
        self.name = name
        self.statNames = attrNames
        self.modType = bonusType #0 makes no stat changes
        self.status = 2 #[destroyed, damaged, good]
        self.statsArray = statChangeList
        self.desc = desc

    def restore(self):
        self.status = 2
    
    def damage(self):
        if self.status > 0:
            self.status -= 1
        else:
            pass

    def repair(self):
        if self.status < 2:
            self.status += 1
        else:
            pass
    
class Cockpit(Module):
    def __init__ (self, name, attrNames, bonusType, statChangeList, pilot, crewServed, desc = ""):
        super().__init__(name, attrNames, bonusType, statChangeList, desc = "")
        self.pilot = pilot
        self.crewServed = crewServed

        #TODO add pilot skills and levels then make them apply
        #TODO add ability for pilot to be injured and incapacitated
    
class Squad:
    def __init__(self, squadName, squadList, squadRole, playerControlled = False):
        self.name = squadName 
        self.mechList = squadList #in order of command
        self.squadLead = self.mechList[0]

        self.role = squadRole
        self.playerControlled = playerControlled
        self.macroObjective = ""
        self.microObjective = ""
        self.Ammo = 0
        self.supplies = 0
        self.effectiveness = 100
        self.reportLog = []

        for mech in self.mechList:
            mech.squad = self

    def roundRefresh(self, matchInfo):
        matchInfo.clearVisuals()
        for entity in self.mechList:
            entity.roundRefresh(matchInfo)
    
    def squadView(self, matchInfo):
        for entity in self.mechList:
            entity.getVisuals(matchInfo)


    def calcEffectiveness(self):
        status = 0
        for mech in self.mechList:
            status += (mech.condition)

        self.effectiveness = (status/len(self.mechList))*100

    def spawnSquad(self, map, spawnPosition):

        mechs = self.mechList
        
        xMinPos = int(spawnPosition[0]-2) #creating a starting range of 5x5 that a mech could spawn
        while  xMinPos < 1:
            xMinPos +=1
        xMaxPos = int(spawnPosition[0]+2)
        while  xMaxPos > len(map)-2:
            xMaxPos -=1
            
        yMinPos = int(spawnPosition[1]-2)
        while  yMinPos < 1:
            yMinPos +=1
        yMaxPos = int(spawnPosition[1]+2)
        while  yMaxPos > len(map)-2:
            yMaxPos -=1

        validSpawnLocations = [] #adds valid spawn points in that range
        for rows in map[yMinPos:yMaxPos]:
            for cell in rows[xMinPos:xMaxPos]:
                if cell.terrain.passable == True and cell.terrain.requireFloat == False:
                    validSpawnLocations.append(list(cell.pos))
            
        while len(validSpawnLocations) <= len(mechs): #expand spawn area if not enough valid cells
            if xMinPos > 2:
                    xMinPos -= 1
            if xMaxPos < len(map)-3:
                    xMaxPos += 1
            if yMinPos > 2:
                    yMinPos -= 1
            if yMaxPos < len(map)-3:
                    yMaxPos += 1

        for mech in mechs:
            spawnPosition = random.choice(validSpawnLocations)
            mech.pos = random.choice(validSpawnLocations)
            validSpawnLocations.remove(spawnPosition)
                




class Team:
    def __init__(self, teamName, squadsList, playerControlled = False):
        self.name = teamName
        self.squadsList = squadsList
        self.resources = 0
        self.reportLog = []
        self.playerControlled = playerControlled

        for squads in self.squadsList:
            squads.team = self.name
            for mech in squads.mechList:
                mech.team = self
