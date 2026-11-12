"""Terrain definitions and cells that make up a generated map."""

import math

from termcolor import colored, cprint
from .radar import entity_detection_threshold


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
        mapHeight = len(map)
        mapWidth = len(map[0])
        if (self.pos[1] + 1 < mapHeight) and (self.pos[0] - 1 >= 0):
            self.nList.append(map[self.pos[1] + 1][self.pos[0] - 1])  # north west
        if self.pos[1] + 1 < mapHeight:
            self.nList.append(map[self.pos[1] + 1][self.pos[0]])  # north
        if (self.pos[1] + 1 < mapHeight) and (self.pos[0] + 1 < mapWidth):
            self.nList.append(map[self.pos[1] + 1][self.pos[0] + 1])  # north east
        if self.pos[0] - 1 >= 0:
            self.nList.append(map[self.pos[1]][self.pos[0] - 1])  # west
        if self.pos[0] + 1 < mapWidth:
            self.nList.append(map[self.pos[1]][self.pos[0] + 1])  # east
        if (self.pos[1] - 1 >= 0)  and (self.pos[0] - 1 >= 0):
            self.nList.append(map[self.pos[1] - 1][self.pos[0] - 1])  # south west
        if self.pos[1] - 1 >= 0:
            self.nList.append(map[self.pos[1] - 1][self.pos[0]])  # south
        if (self.pos[1] - 1 >= 0) and (self.pos[0] + 1 < mapWidth):
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
