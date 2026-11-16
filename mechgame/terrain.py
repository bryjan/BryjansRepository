"""Terrain definitions and cells that make up a generated map."""

import math
from collections import deque

from termcolor import colored, cprint
from .radar import entity_detection_threshold


def mountain_launcher_range_bonus(match_info, position):
    """Return +1 at a mountain edge and +2 one or more tiles into a patch."""
    start = match_info.map[position[1]][position[0]]
    if start.terrain.name != "mountain":
        return 0

    # Depth counts mountain-to-mountain steps before reaching open terrain.
    # A boundary mountain therefore has depth 0 and earns +1 range.
    visited = {id(start)}
    frontier = deque([(start, 0)])
    while frontier:
        cell, depth = frontier.popleft()
        for neighbor in cell.nList:
            if neighbor.terrain.name != "mountain":
                return min(2, depth + 1)
            if id(neighbor) not in visited:
                visited.add(id(neighbor))
                frontier.append((neighbor, depth + 1))
    return 0


#key descriptions in dictionary
class TerrainType:
    """Immutable-style description of how a terrain category behaves and renders."""
    def __init__(self, name, symbol, color, size=0, moveCostBySize=None,
                 visualAbsorbtion=0, radarAbsorbtion=0, radarSig=0,
                 requireFloat=False, fireproof=False, passable=True,
                 symbolHighlight="", symbolAttribute=None, overviewWeight=1):
        self.name = name
        self.symbol = symbol
        self.color = color
        self.size = size
        self.moveCost = list(moveCostBySize) if moveCostBySize is not None else []
        self.visAbsorb = visualAbsorbtion
        self.radarAbsorb = radarAbsorbtion
        self.radarSig = radarSig
        self.requireFloat = requireFloat
        self.fireproof = fireproof
        self.symbolAttribute = list(symbolAttribute) if symbolAttribute is not None else []
        self.symbolHighlight = symbolHighlight
        self.passable = passable
        # Strategic-map chunks use weighted terrain votes instead of letting
        # a single rare tile replace an otherwise dominant landscape.
        self.overviewWeight = overviewWeight

    def displayTerrain(self):
        if self.symbolAttribute != [] and self.symbolHighlight != "":
            return cprint(self.symbol, self.color, self.symbolHighlight, attrs=self.symbolAttribute, end=" ")
        elif self.symbolHighlight != "":
            return cprint(self.symbol, self.color, self.symbolHighlight, end=" ")
        elif self.symbolAttribute != []:
            return cprint(self.symbol, self.color, attrs=self.symbolAttribute, end=" ")
        else:
            return print(colored(self.symbol, self.color), end=" ")


class Cell:
    """One map location, including its terrain, neighbors, and transient sensor data."""
    def __init__ (self, terrainType, xyPosition):
        self.terrain = terrainType
        self.pos = xyPosition
        self.nList = [] #list of neighbor positions for calculations

        self.effects = []
        self.onFire = 0
        self.onSmoke = 0
        self.onChaff = 0
        self.EnergyShieldValue = 0
        self.radarPower = 0
        self.visualPower = 0
        self.canSee = False
        self.radarReturn = False

    def refresh_effect_flags(self):
        """Keep legacy flags synchronized with the object-based effect list."""
        self.onFire = sum(effect.name == "fire" for effect in self.effects)
        self.onSmoke = sum(effect.name == "smoke" for effect in self.effects)
        self.onChaff = sum(effect.name == "chaff" for effect in self.effects)

    @property
    def visualAbsorption(self):
        """Return terrain absorption plus active smoke and similar effects."""
        return self.terrain.visAbsorb + sum(effect.visual_absorption for effect in self.effects)

    @property
    def radarAbsorption(self):
        """Return terrain radar loss plus active smoke and similar effects."""
        return self.terrain.radarAbsorb + sum(effect.radar_absorption for effect in self.effects)
        
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
    
    def displayCell(self, matchInfo): #TODO what will the cell print on map. smoke and fire affects will be displayed through here too
        """Render the visible entity at this cell, or fall back to terrain."""
        for entity in matchInfo.entities:
            if entity.pos == self.pos:
                entity.displayObject(active=entity is matchInfo.pov)
                return
        if self.effects:
            # Fire is drawn above its companion smoke so an active blaze is
            # immediately legible while retaining smoke's sensor penalties.
            effect = next(
                (effect for effect in self.effects if effect.name == "fire"),
                self.effects[-1],
            )
            print(colored(effect.symbol, effect.color), end=" ")
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
