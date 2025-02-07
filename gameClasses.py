import math
import copy
import random
from termcolor import colored, cprint #print(colored(string, color as string),attrs=[bold,dark,underline,blink,reverse,concealed],end='')

class MatchInfo:
    def __init__(self, mapSize, windowSize, teams, mapParams):
        
        self.mapSize = mapSize
        self.windowSize = windowSize
        self.teamList = teams
        self.playerSquad = ""
        self.entities = []
        self.matchRound = 0
        self.pov = ""
        self.mapParamsList = mapParams
        self.map = []
        self.advTurn = False #did POV take a turn ending action (ap costing). reading reports dont advance the turn, moving would, ect.

        self.blank = TerrainType("blank", " ", "black", size= 0, moveCostBySize = [], visualAbsorbtion = 9999, radarAbsorbtion = 9999, fireproof = True, passable = False)
        self.border = TerrainType("border", "X", "white", size= 0, moveCostBySize = [9999,9999,9999,9999,9999,9999,9999], visualAbsorbtion = 1, radarAbsorbtion =1, radarSig = 1, fireproof = True, passable = False)
        self.desert = TerrainType("desert", "~", "yellow", size= 0, moveCostBySize = [1,1,1,1,1,1,1], visualAbsorbtion = 1, radarAbsorbtion = 1, radarSig=9999, fireproof = True)
        self.plains = TerrainType("plains", "_", "light_green", size= 0, moveCostBySize = [1,1,1,1,1,1,1], visualAbsorbtion = 1, radarAbsorbtion = 1,radarSig=9999)
        self.forest = TerrainType("forest", "t", "green", size= 2, moveCostBySize = [1,1,3,2,2,1,1], visualAbsorbtion = 5, radarAbsorbtion = 10, radarSig = 15)
        self.road = TerrainType("road", "=", "dark_grey", size= 0, moveCostBySize = [0,0,0,0,0,0,0], visualAbsorbtion = 0, radarAbsorbtion = 0, radarSig=9999, requireFloat = False, fireproof = True)

    def spawnEntities(self):
        pass #TODO

    def nextMechinTeam(self):
        nextMechIndex = self.pov.squad.squadList.index(self.pov) + 1
    
        if nextMechIndex > len(self.pov.squad.squadList)-1:
            nextMechIndex = 0
    
        self.pov = self.pov.squad.squadList[nextMechIndex]
        self.advTurn = False

    def clearVisuals(self):
        for y in self.map:
            for x in y:
                x.canSee = False
                x.visPower = 0
                x.radarReturn = False
                x.radarPower = 0

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
        self.desert.basicTileGen(self.map,"Light")
        self.forest.basicTileGen(self.map,"Normal")
        self.randomRoadGen(self.map,"Normal")

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
        activeCell = map[target1Pos[1]][target1Pos[0]]
        targetCell = map[target2Pos[1]][target2Pos[0]]
        targetCell.terrain = self.road
        activeCell.terrain = self.road

        while activeCell.pos != targetCell.pos and activeCell.pos[0] > 2 and activeCell.pos[0] < len(map)-2 and activeCell.pos[1] > 2 and activeCell.pos[1] < len(map)-2:
            activeCell.terrain = self.road
            activeCell = activeCell.refClosestNeighborTo(targetCell.pos)
        if type(activeCell) == type(""): #for now idk why it keeps grabbing border tiles even after adding boundries
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
            densityMult= densityList.index(density)
            seedingChance = 1 #out of 100
            neighborConversionChance = 50 #out of 100
            for y in map[1:len(map)-1]:
                for cell in y[1:len(y)-1]: #to avoid flipping border tiles
                    if (random.randint(1,100)<seedingChance*densityMult):
                        cell.terrain = self
            
            genLoops=densityMult

            i=0
            while i < genLoops:
                i+=1
                changeQueue=[] #using a neighbors terrain to determine if you flip will cause a slant if you make changes during the loop
                for y in map[2:len(map)-2]:
                    for cell in y[2:len(y)-2]:
                        flipRoll= False
                        for n in cell.nList:
                            if n.terrain == self:
                                flipRoll= True
                        if flipRoll is True:
                            if ((random.randint(1,100)+(i*8))<neighborConversionChance):
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

class TerrainGenParam: #TODO class that set tiles with basic generation rules with their params
    pass


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
        
        if self.radarReturn == True:
            print(colored("?", "white"), end=" ")
            return
    
    def roundRefresh(self): #TODO reset stats that refresh every round ex)radar and visual strength, radar sources then counting down cell effects
        pass

class Entity: #a character on the map
    def __init__(self, mechClass, pilot):
        self.mechClass = copy.deepcopy(mechClass)
        self.pilot = copy.deepcopy(pilot) #a unique name, seperate from the name of the mech in the stats dictionary. eventually should be an object that levels up and adds perks
        
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
        self.radarPower = (self.mechClass.radarPower / (1 + (self.speed * .2 )))

        
        self.moveDirection = "none"
        self.flying = self.mechClass.initFlying
        self.baseRadarSig = self.mechClass.radarSig
        self.radarSig = (self.baseRadarSig / (1 + (self.speed * .3 )))

        self.visibleCells = []
        self.radarIDlist = [] #items in form of [location, size, direction, speed, objectSymbol, ObjectName] level of radar power reveals more info
        self.radarReturn = [self.pos, self.mechClass.size, self.moveDirection, self.speed, self.mechClass.symbol, self.mechClass.name]
  

    def __repr__(self):
        return self.pilot.name
    
    def getVis(self, matchInfo):
        startingCell = matchInfo.map[self.pos[1]][self.pos[0]]
        startingCell.canSee = True

        for y in matchInfo.map:
            for tile in y:
                tile.visPower = 0

        startingCell.visPower = int(self.visPower + 2)
    
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
        mech = self
        map = matchInfo.map
        startingCell = map[mech.pos[1]][mech.pos[0]]
        if mech.radarPower <= 0:
            return
   
        startingCell.radarPower = int(mech.radarPower)
        self.radarIDlist.append(startingCell)
        startingCell.radarReturn = True

        calcList = [] #cells queued to be calced
        dontCalcList = [startingCell] #cells exempt from calcs
    
        for n in startingCell.nList:
            dontCalcList.append(n)
            calcList.append(n)
        
        for cell in calcList:
            dontCalcList.append(cell)
            closestNeighbor = cell.refClosestNeighborTo(startingCell.pos)
            radarLoss = int(closestNeighbor.terrain.radarAbsorb) + round(math.dist(startingCell.pos, cell.pos))
            cell.radarPower = int(closestNeighbor.radarPower) - radarLoss

        if cell.radarPower < 0:
            cell.radarPower = 0

        if cell.radarPower > 0:
            n.radarReturn = True
            for n in cell.nList:
                if not (n in dontCalcList):
                    calcList.append(n)
                    dontCalcList.append(n)

        for obj in matchInfo.entities: #passive radar and radar ID reports
            if map[obj.pos[1]][obj.pos[0]].radarPower >= obj.radarSig:
                if obj.team != mech.team:
                    if obj.passiveRadar == True and map[obj.pos[1]][obj.pos[0]].radarPower >= 25:
                        self.passiveRadarDetect(matchInfo, mech, obj)
                           
                    self.radarReport(matchInfo,map[obj.pos[1]][obj.pos[0]].radarPower, obj)

    def passiveRadarDetect(self, matchInfo,emittor):
        map = matchInfo.map
        repCritical = False
        emittorCell = map[emittor.pos[1]][emittor.pos[0]]

        if self.team.name == emittor.team.name:
            return
        if self.pos.radarPower == 0:
            return
        if self.mechClass.passiveRadar == False:
            return
    
        strength = self.pos.radarPower
        direction = self.pos.refClosestNeighborTo(emittorCell.pos)
        direction = self.pos.nList.index(direction)
    
        if strength >= self.radarSig * 2:
            status = "identified"
            repCritical = True
        elif strength >= self.radarSig:
            status = "noticable"
            repCritical = True
        else:
            status = "undetected"
    
        if direction == 7:
            direction = "north west"
        elif direction == 6:
            direction = "north"
        elif direction == 5:
            direction = "north east"
        elif direction == 4:
            direction = "west"
        elif direction == 3:
            direction = "east"
        elif direction == 2:
            direction = "sout west"
        elif direction == 1:
            direction = "south"
        elif direction == 0:
            direction = "south east"

        self.report(matchInfo, self,"Getting pinged from the "+ direction +". At " +str(strength) + " strength, I'm " + status +".", critical = repCritical)
    
    def radarReport(self, matchInfo, radarPower, target):
    
        targetName = f""
        speed = f""
        if radarPower >= target.radarSig * 2:
            targetName = f" Identified as {target.name},"
            speed = f"Moving at {target.speed} units a turn."
    
        size = "Unkown"
        if radarPower >= target.radarSig * 1.5:
            size = target.sizeStr.capitalize()
            if target.speed == 0:
                moveDirection = f"not moving"
        else:
            moveDir = target.moveDirection
            moveDirection = f"moving {moveDir}"

        message = f"{size} sized object detected on radar!{targetName} At {target.pos} {moveDirection}. {speed}" #constructing message
    
        self.report(matchInfo, matchInfo.pov, message, critical=True)
    
    def getVisuals(self, matchInfo):
        self.getVis(matchInfo)
        self.getRadar(matchInfo)


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
            mech.team.reportLog.insert(0,[report, critical, False])

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


class Pilot:
    def __init__(self, name):
         self.name = name


class MechClass: #a constructed mech not a npc or player
    def __init__(self, name, size, symbol, color, mechHull, mechHelm, mechLeg, limblist=[], description =""):

        #basic details
        self.name = name
        self.symbol = symbol
        self.color = color
        self.size = size
        self.sizeStrList = ["flat", "tiny", "small", "medium", "large", "huge", "titanic"]
        self.sizeStr = self.sizeStrList[size]

        #limb objects
        self.hull = mechHull
        self.helm = mechHelm
        self.legs = mechLeg
        #limbs roughly organized by height off ground
        self.limbList = [self.legs, self.hull]
        for limb in limblist:
            self.limbList.append(limb)
        self.limbList.append(self.helm)

        #initialize limb passed stats
        self.limbsCondition = 0
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

        #retrieve limb passed stats
        for limb in self.limbList:
            self.limbsCondition += limb.limbCon
            if limb.baseRadarSig > 0:
                self.radarSig = (limb.baseRadarSig * limb.multiRadarSig) + limb.bonusRadarSig
            if limb.baseAP > 0:
                self.apMax = (limb.baseAP * limb.baseAP) + limb.bonusAP
            if limb.baseMP > 0:
                self.mpMax = (limb.baseMP * limb.baseMP) + limb.bonusMP
            if limb.baseEnergy > 0:
                self.energyMax = (limb.baseEnergy * limb.multiEnergy) + limb.bonusEnergy
            if limb.baseEnergyGen > 0:
                self.energyGen = (limb.baseEnergyGen * limb.multiEnergyGen) + limb.bonusEnergyGen
            if limb.baseVisPower > 0:
                self.visPower = (limb.baseVisPower * limb.multiVisPower) + limb.bonusVisPower
            if limb.baseRadarPower > 0:
                self.radarPower = (limb.baseRadarPower * limb.multiRadarPower) + limb.bonusRadarPower
            if limb.passiveRadar == True:
                self.passiveRadar = limb.passiveRadar
            if limb.shareData == True:
                self.shareData = limb.shareData
            if limb.canFloat == True:
                self.canFloat = limb.canFloat
            if limb.canFly == True:
                self.canFly = limb.canFly
            if limb.initFly == True:
                self.initFlying = limb.initFly

        self.energy = int(self.energyMax)
        self.condition = self.limbsCondition / len(self.limbList)
        self.ap = int(self.apMax)
        self.mp = int(self.mpMax)

        self.desc = description

    def displayStats(self): #basic stats display for bug fixing. TODO redo to look nicer and adding descriptions for gameplay
        pass

    def statUpdate(self):
        pass

    def statReset(self): #TODO resets mech's stats to default, including its limbs and modules
        pass

    def roundRefresh(self): #TODO refreshes round based stats(AP,MP,moved)and adds round based resources ex.power from powerGen
        pass

        
class MechPart: # super class to mech limbs
    def __init__ (self, name, armor, hp, moduleList, desc = ""):

        self.desc= desc

        self.name = name

        self.bonusArmor = 0
        self.baseArmor = armor
        self.multiArmor = 1
        self.armor = armor
        self.armorCon = (armor) / ((self.baseArmor * self.multiArmor) + self.bonusArmor)

        self.bonusHP = 0
        self.baseHP = hp
        self.multiHP = 1
        self.hp = hp

        self.condition = self.baseArmor

        self.baseAP = 0
        self.bonusAP = 0
        self.multiAP = 1

        self.baseMP = 0
        self.bonusMP = 0
        self.multiMP = 1

        self.baseEnergy = 0
        self.bonusEnergy = 0
        self.multiEnergy = 1

        self.baseEnergyGen = 0
        self.bonusEnergyGen = 0
        self.multiEnergyGen = 1

        self.baseVisPower = 0
        self.bonusVisPower = 0
        self.multiVisPower = 1

        self.baseRadarSig = 0
        self.bonusRadarSig = 0
        self.multiRadarSig = 1

        self.baseRadarPower = 0
        self.bonusRadarPower = 0
        self.multiRadarPower = 1

        self.shareData = False
        self.passiveRadar = False
        self.canFloat = False
        self.canFly = False
        self.initFly = False

        self.moduleStatsDict = {
    "hp": self.baseHP,
    "bonus hp": self.bonusHP,
    "multi hp": self.multiHP,
    "armor": self.baseArmor,
    "bonus armor": self.bonusArmor,
    "multi armor": self.multiArmor,
    "ap": self.baseAP,
    "bonus ap": self.bonusAP,
    "multi ap": self.bonusAP,
    "mp": self.baseMP,
    "bonus mp": self.bonusMP,
    "multi mp": self.multiMP,
    "energy": self.baseEnergy, #Total stored power
    "bonus energy": self.bonusEnergy, #Total stored power
    "multi energy": self.multiEnergy,
    "energyGen": self.baseEnergyGen, #power returned every round
    "bonus energyGen": self.bonusEnergyGen, #power returned every round
    "multi energyGen": self.multiEnergyGen,

    "shareData": self.shareData,
    "visPower": self.baseVisPower, #Higher means it can see further. common tiles absorb 2 visual strength per tile. so 20 visual power = ~10tile view
    "bonus visPower": self.bonusVisPower, #Higher means it can see further. common tiles absorb 2 visual strength per tile. so 20 visual power = ~10tile view
    "multi visPower": self.multiVisPower,
    "radarPower": self.baseRadarPower, #Higher means it can see/detect further. common tiles absorb 2 radar strength per tile. so 200 visual power = ~100tile view
    "bonus radarPower": self.bonusRadarPower, #Higher means it can see/detect further. common tiles absorb 2 radar strength per tile. so 200 visual power = ~100tile view
    "multi radarPower": self.multiRadarPower,
    "radarSig" : self.baseRadarSig, #Determines how high enemy radar needs to be to detect something is there
    "bonus radarSig" : self.bonusRadarSig, #Determines how high enemy radar needs to be to detect something is there
    "multi radarSig" : self.multiRadarSig,
    "passiveRadar": self.passiveRadar, #Mech will report incoming radar strength and directions
    "canFloat": self.canFloat,
    "canFly": self.canFly,
}

        self.modsList = moduleList.copy()
        self.updateModules()

        self.startingArmor = int((self.baseArmor * self.multiArmor) + self.bonusArmor)
        self.armorCon = self.armor / self.startingArmor
        self.startingHP = int((self.baseHP * self.multiHP) + self.bonusHP)
        self.hpCon = self.hp / self.startingHP

        self.limbCon = (self.armorCon * .3) + (self.hpCon * .7)

    def roundRefresh(self):
        pass

    def updateModules(self):
        for m in self.modsList:
            if m.modType == 1:
                self.moduleStatsDict["multi " + m.statKey] = m.statList[m.status]
            if m.modType == 2:
                self.moduleStatsDict["bonus " + m.statKey] = m.statList[m.status]
            if m.modType == 3:
                self.moduleStatsDict[m.statKey] = m.statList[m.status]

            

class Legs(MechPart): #subclass mechpart
    def __init__ (self, name, armor, hp, moduleList, speed, float = False, fly = False, desc = ""): #this will initi the superclass the same sats
        super().__init__(name, armor, hp, moduleList, desc="")
        
        self.baseMP = speed
        self.canFloat = float
        self.canFly = fly
        self.initFly = fly
        

class Hull(MechPart):
    def __init__ (self, name, armor, hp, moduleList, pwrCapacity, pwrGen, radarSig, desc = ""):
        super().__init__(name, armor, hp, moduleList, desc = "")
        
        self.baseRadarSig = radarSig
        self.baseEnergy = pwrCapacity
        self.baseEnergyGen = pwrGen

class Helm(MechPart):
    def __init__ (self, name, armor, hp, moduleList, ap, visualPower, radarPower, desc=""):
        super().__init__(name, armor, hp, moduleList, desc="")
        self.baseAP = ap
        self.baseVisPower = visualPower
        self.baseRadarPower = radarPower

class Module: #supposed to be superclass but couldn't figure it out
    def __init__(self, name, statKey, bonusType, statChangeList, desc = ""): #[destroyed bonus, damaged bonus, good bonus]
        
        self.name = name
        self.statKey = statKey
        #multi bonus = 1, flat bonus = 2, condition = 3
        self.modType = bonusType
        self.status = 2 #[destroyed, damaged, good]
        self.statList = statChangeList
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
    




        
    
class Squad:
    def __init__(self, squadName, squadList, squadRole, playerControlled = False):
        self.name = squadName 
        self.squadList = squadList #in order of command
        self.role = squadRole
        self.playerControlled = playerControlled
        self.macroObjective = ""
        self.microObjective = ""
        self.oAmmo = 0
        self.sAmmo = 0
        self.supplies = 0
        self.effectiveness = 100
        self.reportLog = []

        for mech in self.squadList:
            mech.squad = self

    def squadView(self, matchInfo):
        for entity in self.squadList:
            entity.getVisuals(matchInfo)


    def calcEffectiveness(self):
        status = 0
        for mech in self.squadList:
            status += (mech.condition)

        self.effectiveness = (status/len(self.squadList))*100

    def spawnSquad(self, map, spawnPosition):

        mechs = self.squadList
        
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
            for mech in squads.squadList:
                mech.team = self
