"""Combat domain objects shared by entities, mech parts, and teams.

This module keeps the original combat model together while its responsibilities
are gradually split into focused systems. Map construction lives in
``mechgame.world``; focused modules re-export their public classes from here.
"""

import heapq
import math
import functions as f
import copy
import random
from termcolor import colored, cprint #print(colored(string, color as string),attrs=[bold,dark,underline,blink,reverse,concealed],end='')
from .radar import entity_detection_threshold, radar_step_loss

class MatchInfo:
    """Mutable state shared by one running match.

    It owns the teams, map, turn cursor, and collections of active and removed
    entities. Systems receive this object when they need match-wide context.
    """
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

        # Terrain definitions and map construction live in mechgame.world.
        # These attributes are populated by mapInit for compatibility with the
        # existing combat and rendering code.
        self.blank = self.border = self.desert = self.plains = None
        self.forest = self.suburb = self.road = None

    def spawnEntities(self):
        pass #TODO

    def nextSquadTurn(self):
        """Advance the point of view to the first mech in the next squad."""
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
        """Cycle the point of view through the current squad without ending its turn."""
        nextMechIndex = self.pov.squad.mechList.index(self.pov) + 1
    
        if nextMechIndex > len(self.pov.squad.mechList)-1:
            nextMechIndex = 0
    
        self.pov = self.pov.squad.mechList[nextMechIndex]
        self.advTurn = False

    def clearVisuals(self):
        """Clear per-turn visibility and radar data from every map cell."""
        for y in self.map:
            for x in y:
                x.canSee = False
                x.visPower = 0
                x.radarReturn = False
                x.radarPower = 0

    
    
    def explosion(self, location, radius, size, damage): #spawns explosions. for rockets/artillery
        """Apply area damage to entities within ``radius`` of a map position."""
        
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
        """Return the slope and intercept for a line between two grid positions."""

        x1, y1 = point1
        x2, y2 = point2

        slope = (y1 - y2) / (x1 - x2)
        yIntercept = y1 - (slope * x1)

        return [slope, yIntercept]

    def ListInterceptingSquares(self, point1, point2):
        """Return approximate cells crossed by a line of sight or projectile path."""

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


    def mapInit(self):
        """Build the world through the dedicated map-generation module."""
        from mechgame.world import MapGenerator

        self.map = MapGenerator(self.mapSize).build(self)

#key descriptions in dictionary
class TerrainType:
    """Immutable-style description of how a terrain category behaves and renders."""
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
    """One map location, including its terrain, neighbors, and transient sensor data."""
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
        """Populate adjacent-cell references once the full map grid exists."""
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
        """Render the visible entity at this cell, or fall back to terrain."""
        
        for entity in matchInfo.entities:
            if entity.pos == self.pos:
                entity.displayObject(active=entity is matchInfo.pov)
                return
        else:
            self.terrain.displayTerrain()
            return

    def displayRadarReturn(self, matchInfo):

        for entity in matchInfo.entities:
            threshold = entity_detection_threshold(entity.radarSig)
            if entity.pos == self.pos and self.radarPower >= (threshold * 2):
                entity.displayObject(active=entity is matchInfo.pov)
                return
            if entity.pos == self.pos and self.radarPower >= threshold:
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
    """A pilot-controlled instance of a mech class placed in a match."""
    def __init__(self, mechClass, pilot):
        self.mechClass = copy.deepcopy(mechClass)
        self.mechClass.mech = self

        self.pilot = copy.deepcopy(pilot)
        for limb in self.mechClass.limbList:
            limb.mech = self
        #inserts pilot into mech's Helm
        self.cockpit = Cockpit("Pilot", "multi ap", 3, ["0", ".75", "1"], self.pilot, False)
        self.cockpit.mech = self
        self.mechClass.helm.modsList.append(self.cockpit)

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
        # Active radar starts silent.  The pilot can enable continuous scans or
        # spend energy on a single-turn pulse.
        self.radarOn = False
        self.radarPulseActive = False

        self.turnStartPos = list(self.pos)
        self.flying = self.mechClass.initFlying
        self.baseRadarSig = self.mechClass.radarSig
        self.radarSig = (self.baseRadarSig / (1 + (self.speed * .2 )))

        self.visibleCells = []
        self.radarIDlist = [] #items in form of [location, size, direction, speed, objectSymbol, ObjectName] level of radar power reveals more info

        #ai flags
        self.travelSpeed = max(self.mechClass.apMax, self.mechClass.mpMax)
        self.needrest = False
        # Tactical memory is useful to both AI and the player fire menu.
        self.lastFiredAt = None
        self.directlyVisibleEnemies = []
        self.trackedEnemies = []

        # A destroyed cockpit takes the whole mech out of the current match.
        self.destroyed = False
  

    def __repr__(self):
        return self.pilot.name

    def statusReport(self):
        """Return a compact condition report for the player or future AI.

        Parts own their armor, HP, and modules, so this report deliberately
        reads those live values rather than relying on the mech-wide average.
        """
        parts = self.mechClass.limbList
        damagedModules = sum(
            module.status < 2
            for part in parts
            for module in part.modsList
        )
        totalModules = sum(len(part.modsList) for part in parts)
        lines = [
            f"{self.mechClass.name} — {self.pilot.name}",
            f"Overall condition: {round(self.mechClass.condition)}% | "
            f"Damaged modules: {damagedModules}/{totalModules}",
        ]

        for part in parts:
            partDamagedModules = sum(module.status < 2 for module in part.modsList)
            modules = f"modules {partDamagedModules}/{len(part.modsList)} damaged"
            integrity = (
                f"armor {part.armor}/{part.startingArmor} | "
                f"HP {part.hp}/{part.startingHP}"
            )
            weaponInfo = ""
            if part.isGun:
                charges = "unlimited" if part.charges is None else f"{part.charges}/{part.maxCharges}"
                weaponInfo = f" | charges {charges}"
            lines.append(f"- {part.name}: {integrity} | {modules}{weaponInfo}")
        return "\n".join(lines)
    
    def roundRefresh(self, matchInfo):
        """Restore per-round state and refresh the mech's derived statistics."""

        #basic stats
        self.turnStartPos = list(self.pos)
        self.speed = 0

        self.ap = int(self.mechClass.apMax)
        self.mp = int(self.mechClass.mpMax)

        # A pulse only lasts for the squad turn in which it was ordered.
        if self.radarPulseActive:
            self.radarOn = False
            self.radarPulseActive = False

        self.energy += self.mechClass.energyGen
        if self.energy > self.mechClass.energyMax:
            self.energy = int(self.mechClass.energyMax)

        # Sustained radar pays its scan cost every turn after its activation.
        # It shuts down rather than allowing the energy reserve to go negative.
        if self.radarOn and not self._spend_radar_energy():
            self.radarOn = False
            self.report(matchInfo, "Radar shut down: insufficient energy.")

        #get visuals
        self.getVisuals(matchInfo)

        #ai flags calc
        if self.ap == 0 or self.mp == 0 or self.energy <= (self.mechClass.energyMax * .4):
            self.needrest = True


    
    def moveMech(self, matchInfo, input):
        """Attempt one keyboard-directed move and charge the required movement points."""
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

    def _spend_radar_energy(self):
        """Spend the configured radar scan cost when the reserve can cover it."""
        cost = self.mechClass.radarEnergyCost
        if self.energy < cost:
            return False
        self.energy -= cost
        return True

    def toggleRadar(self, matchInfo):
        """Enable or disable continuous active radar for the current mech."""
        if self.radarOn:
            self.radarOn = False
            matchInfo.clearRadar()
            print("Continuous radar off.")
            return

        if self.mechClass.radarPower <= 0:
            print("This mech has no active radar.")
            return
        if not self._spend_radar_energy():
            print("Not enough energy to activate continuous radar.")
            return

        self.radarOn = True
        self.radarPulseActive = False
        print("Continuous radar on.")

    def pulseRadar(self, matchInfo):
        """Enable radar for this squad turn, then shut it down automatically."""
        if self.mechClass.radarPower <= 0:
            print("This mech has no active radar.")
            return
        if self.radarOn:
            print("Continuous radar is already active.")
            return
        if not self._spend_radar_energy():
            print("Not enough energy for a radar pulse.")
            return

        self.radarOn = True
        self.radarPulseActive = True
        print("Radar pulse sent.")
    
    def getVis(self, matchInfo):
        """Project this entity's visual range through terrain absorption."""
        startingCell = matchInfo.map[self.pos[1]][self.pos[0]]
        startingCell.canSee = True
        # Rebuild personal line-of-sight data each refresh. Map cells also
        # retain squad vision for rendering, but fire choices need this mech's
        # own currently visible enemies.
        self.visibleCells = [startingCell]

        for y in matchInfo.map:
            for tile in y:
                tile.visPower = 0

        startingCell.visPower = int(self.visPower + startingCell.terrain.visAbsorb)
    
        calcList = [] #cells queued to be calced
        dontCalcList= [startingCell] #cells exempt from calcs
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
                self.visibleCells.append(cell)
                for n in cell.nList:
                    if (n not in dontCalcList):
                        calcList.append(n)
                        dontCalcList.append(n)

        self.directlyVisibleEnemies = [
            entity
            for entity in matchInfo.entities
            if entity.team != self.team
            and matchInfo.map[entity.pos[1]][entity.pos[0]] in self.visibleCells
        ]
        self._refresh_tracked_enemies()

    def _refresh_tracked_enemies(self):
        """Combine this mech's own vision with contacts shared by its squad."""
        radarContacts = getattr(self.squad, "radarTrackedEnemies", [])
        self.trackedEnemies = list(dict.fromkeys([*self.directlyVisibleEnemies, *radarContacts]))

    def getRadar(self, matchInfo):
        """Refresh shared active-radar coverage when a source state changed."""
        matchInfo.refreshRadar()

    def _projectRadar(self, matchInfo):
        """Project one source through terrain using the strongest available path."""
        map = matchInfo.map
        startingCell = map[self.pos[1]][self.pos[0]]
        sourcePower = int(self.mechClass.radarPower / (1 + (self.speed * .25)))
        if sourcePower <= 0:
            return

        # Radar below this strength cannot create a passive-radar warning or
        # any current terrain/entity contact, so there is no reason to expand.
        propagationCutoff = 25
        bestPower = {tuple(startingCell.pos): sourcePower}
        frontier = [(-sourcePower, 0, startingCell)]
        sequence = 1
        self.radarPower = sourcePower
        self.radarIDlist = [startingCell]

        while frontier:
            negativePower, _, cell = heapq.heappop(frontier)
            power = -negativePower
            if power != bestPower.get(tuple(cell.pos)):
                continue

            cell.radarPower = max(cell.radarPower, power)
            cell.radarReturn = True

            for neighbor in cell.nList:
                nextPower = power - radar_step_loss(neighbor.terrain.radarAbsorb)
                neighborPos = tuple(neighbor.pos)
                if nextPower < propagationCutoff or nextPower <= bestPower.get(neighborPos, -1):
                    continue
                bestPower[neighborPos] = nextPower
                heapq.heappush(frontier, (-nextPower, sequence, neighbor))
                sequence += 1

        radarContacts = []
        for obj in matchInfo.entities: #passive radar and radar ID reports
            contactPower = bestPower.get(tuple(obj.pos), 0)
            if obj.mechClass.passiveRadar == True and contactPower >= propagationCutoff:
                if obj.team != self.team:
                    obj.passiveRadarDetect(matchInfo, self)
            if contactPower >= entity_detection_threshold(obj.radarSig):
                if obj.team != self.team:
                    radarContacts.append(obj)
                    self.radarReport(matchInfo, contactPower, obj)

        # Radar contacts belong to the squad, not only the mech that emitted
        # the scan. Preserve contacts from other active friendly radars too.
        for contact in radarContacts:
            if contact not in self.squad.radarTrackedEnemies:
                self.squad.radarTrackedEnemies.append(contact)

    def passiveRadarDetect(self, matchInfo, emittor):
        """Try to detect an emitting entity using this mech's passive radar."""
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
        # ``self`` is the detecting mech.  Referring to ``self.entity`` here
        # crashed as soon as active radar reached a passive detector.
        if self.speed > 1:
            return 
    
        strength = map[self.pos[1]][self.pos[0]].radarPower

        threshold = entity_detection_threshold(self.radarSig)
        if strength >= threshold * 2:
            status = "identified"
            repCritical = True
        elif strength >= threshold:
            status = "noticable"
            repCritical = True
        else:
            status = "undetected"

        return self.report(matchInfo,"Getting pinged from the " + direction + ". At " + str(strength) + " strength, I'm " + status + ".", critical = repCritical)
    
    def radarReport(self, matchInfo, radarPower, target):
        """Record an imprecise radar contact for the target's squad."""

        threshold = entity_detection_threshold(target.radarSig)
        if radarPower < threshold:
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

        if radarPower >= threshold * 2:
            targetName = f" Identified as {target.mechClass.name},"
            speed = f" Moving at {target.speed} units a turn."
    
        if radarPower >= threshold * 1.5:
            size = target.sizeStr.capitalize()
            if target.speed == 0:
                moveDirection = f", not moving"
            
        message = f"{size} sized object detected on radar!{targetName} At {target.pos}{moveDirection}.{speed}" #constructing message
    
        self.report(matchInfo, message, critical = True)
    
    def getVisuals(self, matchInfo):
        """Update both visual and radar information for the current entity."""
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

    def displayObject(self, active=False):
        """Render a mech symbol, emphasizing the currently controlled mech."""
        attributes = ["bold", "reverse", "blink"] if active else []
        return print(colored(self.mechClass.symbol, self.mechClass.color, attrs=attributes), end=" ")

    def destroy(self, matchInfo):
        """Remove this mech from active play and record its destruction once."""
        if self.destroyed:
            return

        self.destroyed = True
        if self in matchInfo.entities:
            matchInfo.entities.remove(self)
        if self.squad and self in self.squad.mechList:
            self.squad.mechList.remove(self)
        if self not in matchInfo.destroyedMechs:
            matchInfo.destroyedMechs.append(self)

        # A destroyed active mech cannot continue taking actions this turn.
        if matchInfo.pov is self:
            matchInfo.turnEnded = True


class Pilot: #TODO add pilot levels, skills, certs
    """Named crew member assigned to an entity."""
    def __init__(self, name):
         self.name = name


class MechClass: #a constructed mech not a npc or player
    """Reusable mech blueprint composed from hull, helm, legs, and weapon limbs."""
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
        self.radarEnergyCost = 0
        self.passiveRadar = False
        self.canfloat = False
        self.canFly = False
        self.initFlying = False

        self.passedStatsList = ["size","radarSig","apMax","mpMax","energyMax","energyGen","shareData","visPower","radarPower","radarEnergyCost","passiveRadar","canFly","canFloat","initFlying"]

        self.statUpdate()

        self.condition = sum(self.limbsConditionList) / len(self.limbsConditionList) * 100
        self.sizeStrList = ["flat", "tiny", "small", "medium", "large", "huge", "titanic"]
        self.sizeStr = self.sizeStrList[self.size]

        self.desc = description

    def displayStats(self): #basic stats display for bug fixing. TODO redo to look nicer and adding descriptions for gameplay
        pass

    def statUpdate(self):
        """Recalculate derived mech statistics after a part or module changes."""
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
        """Restore action and movement resources for a new round."""
        pass

        
class MechPart: # super class to mech limbs
    """Base component with armor, hit points, modules, and derived modifiers."""
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
        """Apply this part's active module modifiers to its target attributes.

        Module stat arrays are indexed by module condition: destroyed (0),
        damaged (1), then intact (2).
        """
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
        """Resolve damage against armor and hit points, then check critical effects."""

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
        dmgdMod.damage(matchInfo)
        self.mechClass.statUpdate()
        # Damaged modules can lower live resource limits immediately. Clamp the
        # current values so a mech cannot keep capacity or movement it lost.
        self.mech.energy = min(self.mech.energy, self.mechClass.energyMax)
        self.mech.mp = min(self.mech.mp, self.mechClass.mpMax)
            

class Legs(MechPart): #subclass mechpart
    """Mech part that contributes mobility and optional floating or flight."""
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
    """Mech part that supplies power, signature, and chassis size."""
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
        self.energyMax = (self.baseEnergy * self.multiEnergy) + self.bonusEnergy

        self.baseEnergyGen = pwrGen
        self.bonusEnergyGen = 0
        self.multiEnergyGen = 1
        self.energyGen = (self.baseEnergyGen * self.multiEnergyGen) + self.bonusEnergyGen

    def updateHullStats(self):
        self.radarSig = int((self.baseRadarSig * self.multiRadarSig) + self.bonusRadarSig)
        self.energyMax = int((self.baseEnergy * self.multiEnergy) + self.bonusEnergy)
        self.energyGen = int((self.baseEnergyGen * self.multiEnergyGen) + self.bonusEnergyGen)


class Helm(MechPart):
    """Mech part that supplies action points and sensor power."""
    def __init__ (self, name, armor, hp, moduleList, ap, visualPower, radarPower, radarEnergyCost=0, desc=""):
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

        self.baseRadarEnergyCost = radarEnergyCost
        self.bonusRadarEnergyCost = 0
        self.multiRadarEnergyCost = 1
        self.radarEnergyCost = (self.baseRadarEnergyCost * self.multiRadarEnergyCost) + self.bonusRadarEnergyCost

        self.shareData = True
        self.passiveRadar = False

    def updateHelmStats(self):
        self.apMax = int((self.baseAP * self.multiAP) + self.bonusAP)
        self.visPower = int((self.baseVisPower * self.multiVisPower) + self.bonusVisPower)
        self.radarPower = int((self.baseRadarPower * self.multiRadarPower) + self.bonusRadarPower)
        self.radarEnergyCost = int((self.baseRadarEnergyCost * self.multiRadarEnergyCost) + self.bonusRadarEnergyCost)


class WeaponLimb(MechPart):
    """Arm-mounted weapon with ammunition, costs, accuracy, and damage stats."""
    def __init__ (self, name, armor, hp, moduleList, damage, accuracy, soundRep, charges, projectileCount = 1, apCost = 1, energyCost = 0, speedPenalty = 8, armorPiercing = False, armorDamage = 0, maxRange = None, desc = ""):
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

        # Any accuracy-affecting module may change this multiplier. The
        # Holosight is only one example of such a module.
        self.accuracyMultiplier = 1
        self.maxRange = maxRange

    def updateWeaponStats(self):
        self.projectileCount = int((self.baseProjectileCount * self.multiProjectileCount) + self.bonusProjectileCount)
        self.accuracy = int((self.baseAccuracy * self.multiAccuracy) + self.bonusAccuracy)
        self.soundReport = int((self.baseSoundReport * self.multiSoundReport) + self.bonusSoundReport)

    def emitSound(self, matchInfo):
        """Send a sound report to enemy entities within audible range."""
        for entity in matchInfo.entities:
            if math.dist(matchInfo.pov.pos, entity.pos) <= self.soundReport and entity not in matchInfo.pov.squad.mechList:
                entity.report(matchInfo, "I hear shots. Sounds like a " + self.name + "." , teamReport = False, critical = False)
    
    def shootAt(self, matchInfo, pos, aimedLimb=None):
        """Spend resources and resolve every projectile fired at a map position."""

        #check if enough resources
        if self.charges is not None and self.charges - 1 < 0:
            print("Out of ammo!")
            return
        if self.maxRange is not None and math.dist(matchInfo.pov.pos, pos) > self.maxRange:
            print(f"Target is beyond this weapon's {self.maxRange}-tile range.")
            return
        aimApCost = 1 if aimedLimb is not None else 0
        if matchInfo.pov.ap - (self.apCost + aimApCost) < 0:
            print("Out of action points!")
            return
        if matchInfo.pov.energy - self.energyCost < 0:
            print("Not enough energy to fire!")
            return

        if self.charges is not None:
            self.charges -= 1
        matchInfo.pov.ap -= self.apCost + aimApCost
        matchInfo.pov.energy -= self.energyCost
        # Store the attempted location even on a miss so a follow-up shot can
        # be ordered without re-entering coordinates.
        matchInfo.pov.lastFiredAt = list(pos)
        
        #enemies will report noise
        self.emitSound(matchInfo)

        #Calculates shot based on terrain between you and target, ignores the tile you're standing on and directly infront
        path = matchInfo.ListInterceptingSquares(matchInfo.pov.pos, pos)
        startingCell = matchInfo.map[matchInfo.pov.pos[1]][matchInfo.pov.pos[0]]
        removeList = [*startingCell.nList, startingCell]

        for cell in removeList:
            if cell in path:
                path.remove(cell)

        accuracyRequired = 0
        for n in path:
            accuracyRequired += n.terrain.visAbsorb

        target = next((entity for entity in matchInfo.entities if entity.pos == pos), None)

        i = 1
        while i <= self.projectileCount:
            i += 1
            movementMultiplier = 1
            if matchInfo.pov.speed > 0:
                movementMultiplier = 1 - ((random.randint(0, self.speedPenalty) * matchInfo.pov.speed) / 100)
            effectiveAccuracy = self.accuracy * self.accuracyMultiplier * movementMultiplier
            hitChance = self._hit_chance(matchInfo.pov, target, effectiveAccuracy, accuracyRequired)

            if random.randint(1, 100) > hitChance:
                print("Shot missed!")
            else:
                print("Shot hit!")
                if target is not None:
                    targetLimb = aimedLimb if aimedLimb in target.mechClass.limbList else random.choice(target.mechClass.limbList)
                    targetLimb.damage(matchInfo, self.dmg, self.name, armorPiercing = self.piercing, armorDamage = self.armorDamage)

        matchInfo.advTurn = True

    def _hit_chance(self, shooter, target, effectiveAccuracy, accuracyRequired):
        """Return the per-projectile hit chance after terrain and size effects."""
        if effectiveAccuracy < accuracyRequired:
            return 0

        # Meeting the terrain requirement creates the first 10% chance. Every
        # further point adds 5%, then target size modifies the final result.
        baseChance = 10 + ((effectiveAccuracy - accuracyRequired) * 5)
        targetSize = target.size if target is not None else shooter.size
        sizeMultiplier = 1.2 ** (targetSize - shooter.size)
        return min(99, max(10, round(baseChance * sizeMultiplier)))

    def printShortDesc(self):

        charges = "Unlimited" if self.charges is None else f"{self.charges}/{self.maxCharges}"
        return f"[{self.name} | Charges:({charges}) AP Cost:{self.apCost} Energy Cost:{self.energyCost}]"


#clean up module system and make it work (not updating)
class Module: #supposed to be superclass but couldn't figure it out
    """Damageable modifier attached to a mech part."""
    def __init__(self, name, attrNames, bonusType, statChangeList, desc = ""): #[destroyed bonus, damaged bonus, good bonus]
        
        self.name = name
        self.statNames = attrNames
        self.modType = bonusType #0 makes no stat changes
        self.status = 2 #[destroyed, damaged, good]
        self.statsArray = statChangeList
        self.desc = desc

    def restore(self):
        self.status = 2
    
    def damage(self, matchInfo=None):
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
    """Module that records the pilot and crew required to operate a mech."""
    def __init__ (self, name, attrNames, bonusType, statChangeList, pilot, crewServed, desc = ""):
        super().__init__(name, attrNames, bonusType, statChangeList, desc = "")
        self.pilot = pilot
        self.crewServed = crewServed
        self.mech = None

        #TODO add pilot skills and levels then make them apply

    def damage(self, matchInfo=None):
        """Warn on pilot injury and destroy the mech when the cockpit fails."""
        previous_status = self.status
        super().damage(matchInfo)

        if matchInfo is None or self.mech is None or previous_status == self.status:
            return

        if self.status == 1:
            self.mech.report(
                matchInfo,
                "Cockpit hit! Pilot injured; cockpit integrity is failing.",
                critical=True,
            )
        elif self.status == 0:
            self.mech.report(
                matchInfo,
                "Cockpit destroyed! Mech is no longer operational.",
                critical=True,
            )
            self.mech.destroy(matchInfo)
    
class Squad:
    """Ordered group of mechs that acts together and shares intelligence."""
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
        # Active-radar contacts are shared by every mech in this squad.
        self.radarTrackedEnemies = []

        for mech in self.mechList:
            mech.squad = self

    def roundRefresh(self, matchInfo):
        """Refresh every squad member at the beginning of its round."""
        matchInfo.clearVisuals()
        self.radarTrackedEnemies = []
        for entity in self.mechList:
            entity.roundRefresh(matchInfo)

    def statusReport(self):
        """Return a squad readiness summary for the player or future AI."""
        if not self.mechList:
            return f"{self.name}: no operational mechs remain."

        averageIntegrity = sum(mech.mechClass.condition for mech in self.mechList) / len(self.mechList)
        damagedModules = sum(
            module.status < 2
            for mech in self.mechList
            for part in mech.mechClass.limbList
            for module in part.modsList
        )
        totalModules = sum(
            len(part.modsList)
            for mech in self.mechList
            for part in mech.mechClass.limbList
        )
        mostDamaged = min(self.mechList, key=lambda mech: mech.mechClass.condition)

        ammoByWeapon = {}
        for mech in self.mechList:
            for weapon in mech.mechClass.gunList:
                ammunition = ammoByWeapon.setdefault(
                    weapon.name,
                    {"current": 0, "maximum": 0, "unlimited": False},
                )
                if weapon.charges is None:
                    ammunition["unlimited"] = True
                    continue
                ammunition["current"] += weapon.charges
                ammunition["maximum"] += weapon.maxCharges

        ammoSummary = []
        for weaponName, ammo in ammoByWeapon.items():
            amount = "unlimited" if ammo["unlimited"] else f"{ammo['current']}/{ammo['maximum']}"
            ammoSummary.append(f"{weaponName} {amount}")
        ammunition = ", ".join(ammoSummary) if ammoSummary else "none"

        return "\n".join([
            f"{self.name} squad status",
            f"Average integrity: {round(averageIntegrity)}% | Damaged modules: {damagedModules}/{totalModules}",
            f"Ammunition: {ammunition}",
            f"Most damaged: {mostDamaged.pilot.name} — {mostDamaged.mechClass.name} ({round(mostDamaged.mechClass.condition)}%)",
        ])
    
    def squadView(self, matchInfo):
        for entity in self.mechList:
            entity.getVisuals(matchInfo)


    def calcEffectiveness(self):
        status = 0
        for mech in self.mechList:
            status += (mech.condition)

        self.effectiveness = (status/len(self.mechList))*100

    def spawnSquad(self, map, spawnPosition):
        """Place squad members on nearby passable, non-floating terrain cells."""

        mechs = self.mechList
        mapHeight = len(map)
        mapWidth = len(map[0])
        
        xMinPos = int(spawnPosition[0]-2) #creating a starting range of 5x5 that a mech could spawn
        while  xMinPos < 1:
            xMinPos +=1
        xMaxPos = int(spawnPosition[0]+2)
        while  xMaxPos > mapWidth-2:
            xMaxPos -=1
            
        yMinPos = int(spawnPosition[1]-2)
        while  yMinPos < 1:
            yMinPos +=1
        yMaxPos = int(spawnPosition[1]+2)
        while  yMaxPos > mapHeight-2:
            yMaxPos -=1

        validSpawnLocations = [] #adds valid spawn points in that range
        for rows in map[yMinPos:yMaxPos]:
            for cell in rows[xMinPos:xMaxPos]:
                if cell.terrain.passable == True and cell.terrain.requireFloat == False:
                    validSpawnLocations.append(list(cell.pos))
            
        while len(validSpawnLocations) <= len(mechs): #expand spawn area if not enough valid cells
            if xMinPos > 2:
                    xMinPos -= 1
            if xMaxPos < mapWidth-3:
                    xMaxPos += 1
            if yMinPos > 2:
                    yMinPos -= 1
            if yMaxPos < mapHeight-3:
                    yMaxPos += 1

        for mech in mechs:
            spawnPosition = random.choice(validSpawnLocations)
            mech.pos = random.choice(validSpawnLocations)
            validSpawnLocations.remove(spawnPosition)
                




class Team:
    """Collection of squads with a shared name, resources, and report log."""
    def __init__(self, teamName, squadsList, playerControlled = False):
        self.name = teamName
        self.squadsList = squadsList
        self.resources = 0
        self.reportLog = []
        self.playerControlled = playerControlled

        for squads in self.squadsList:
            # Keep the object reference: turn sequencing needs its squad list.
            squads.team = self
            for mech in squads.mechList:
                mech.team = self
