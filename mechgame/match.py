"""Match-wide state and turn-independent board calculations."""

import math


class MatchInfo:
    """Mutable state shared by one running match."""

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

        nextTeamIndex = teamIndex
        nextSquadIndex = squadIndex + 1
        if nextSquadIndex >= len(self.pov.team.squadsList):
            nextSquadIndex = 0
            nextTeamIndex += 1

        if nextTeamIndex >= len(self.teamList): #start of new round
            self.matchRound += 1
            #TODO refresh round stats
            nextTeamIndex = 0

        # Sensor information is rebuilt for the squad that is about to act.
        self.clearVisuals()
        self.pov = self.teamList[nextTeamIndex].squadsList[nextSquadIndex].mechList[0]
        self.pov.squad.roundRefresh(self)
        self.advTurn = False

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

        for i in range(min(point1[1], point2[1]), max(point1[1], point2[1]) + 1):
            x = round((i - intercept) / slope)
            interceptingCells.append(self.map[x][i])
        return interceptingCells

    def mapInit(self):
        """Build the world through the dedicated map-generation module."""
        from mechgame.world import MapGenerator
        self.map = MapGenerator(self.mapSize).build(self)
