"""Match-wide state and turn-independent board calculations."""

import math
import random

from . import artillery
from . import effects
from . import radar


class MatchInfo:
    """Mutable state shared by one running match."""

    def __init__(self, mapSize, windowSize, teams, mapParams, mapHeight=None):
        # ``mapSize`` remains the width for compatibility with older callers.
        # Height defaults to width so existing square-map games still work.
        self.mapSize = mapSize
        self.mapWidth = mapSize
        self.mapHeight = mapSize if mapHeight is None else mapHeight
        self.windowSize = windowSize
        self.teamList = teams #team0 are nuetral entities
        self.playerSquad = ""
        self.entities = []
        self.abandonedMechs = []
        self.destroyedMechs = []
        # Fired launcher shells resolve only after future squad-turn handoffs.
        self.pendingImpacts = []
        self.matchRound = 0
        self.pov = ""
        self.mapParamsList = mapParams
        self.map = []
        # Radar coverage is cached until a source changes in a meaningful way.
        self._radarSourceState = None
        self.advTurn = False #did POV take a turn ending action (ap costing). reading reports dont advance the turn, moving would, ect.
        # advTurn records an action; turnEnded is reserved for the player's
        # explicit request to hand control to the next squad.
        self.turnEnded = False

        # Terrain definitions and map construction live in mechgame.world.
        # These attributes are populated by mapInit for compatibility with the
        # existing combat and rendering code.
        self.blank = self.border = self.desert = self.plains = None
        self.forest = self.suburb = self.road = None

    def spawnEntities(self):
        pass #TODO

    def nextSquadTurn(self):
        """Advance the point of view to the first mech in the next squad."""
        # A pulse is active only for the squad turn in which it was ordered.
        # Clear every squad member so changing the point of view cannot let a
        # previous pilot's pulse survive into the next squad turn.
        for mech in self.pov.squad.mechList:
            if mech.radarPulseActive:
                mech.radarOn = False
                mech.radarPulseActive = False

        teamIndex = self.teamList.index(self.pov.team)
        squadIndex = self.pov.team.squadsList.index(self.pov.squad)

        nextTeamIndex = teamIndex
        nextSquadIndex = squadIndex + 1
        if nextSquadIndex >= len(self.pov.team.squadsList):
            nextSquadIndex = 0
            nextTeamIndex += 1

        if nextTeamIndex >= len(self.teamList): #start of new round
            self.matchRound += 1
            effects.advance_effects(self)
            # Radar contacts are tactical memory for one full match round.
            # They survive friendly squad changes, then expire together when a
            # fresh round begins.
            for team in self.teamList:
                team.radarContacts.clear()
            nextTeamIndex = 0

        # Sensor information is rebuilt for the squad that is about to act.
        self.clearVisuals()
        self.pov = self.teamList[nextTeamIndex].squadsList[nextSquadIndex].mechList[0]
        self.pov.squad.roundRefresh(self)

        # Resolve shells only after the new squad has been selected.  This
        # makes impacts belong to the new turn and prevents fresh smoke or
        # fire from being immediately aged during a round-boundary refresh.
        artillery.advance_impacts(self)
        self.advTurn = False
        self.turnEnded = False

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
        self.clearRadar()

    def clearRadar(self, invalidate=True):
        """Clear radar returns without disturbing ordinary line of sight."""
        radar.clear_returns(self, invalidate)

    def refreshRadar(self):
        """Rebuild active radar only after a detectable source-state change."""
        radar.refresh(self)

    def explosion(self, location, radius, size, damage, soundRange=0):
        """Apply blast damage to several random parts of each mech in range."""
        self._report_explosion(location, soundRange)
        for entity in list(self.entities):
            if math.dist(location, entity.pos) > radius:
                continue

            # Larger explosions can strike more parts; large targets spread the
            # blast across more armor, while small targets are more exposed.
            parts_to_hit = max(1, min(len(entity.mechClass.limbList), 3 + size - entity.size))
            # Every fragment hit strips one armor point. Blast size changes
            # the number of limbs exposed, not the armor removed per limb.
            armor_damage = 1
            for limb in random.sample(entity.mechClass.limbList, parts_to_hit):
                limb.damage(self, damage, "explosion", armorDamage=armor_damage)

        # TODO: explosions can later add fire, smoke, and terrain effects.

    def _report_explosion(self, location, soundRange):
        """Let nearby mechs report an impact they saw or heard.

        Visual confirmation is urgent information, so it produces a critical
        report.  Hearing alone still gives a useful, ordinary warning without
        revealing the exact impact location to a squad that could not see it.
        """
        for entity in self.entities:
            sees_impact = entity.pos == location or any(
                cell.pos == location for cell in entity.visibleCells
            )
            if sees_impact:
                entity.report(
                    self, f"I see an explosion at {location}.",
                    teamReport=False, critical=True,
                )
            elif soundRange > 0 and math.dist(entity.pos, location) <= soundRange:
                entity.report(
                    self, "I hear an explosion.",
                    teamReport=False, critical=False,
                )

    def calcLine(self, point1, point2):
        """Return the slope and intercept for a line between two grid positions."""
        x1, y1 = point1
        x2, y2 = point2
        slope = (y1 - y2) / (x1 - x2)
        yIntercept = y1 - (slope * x1)
        return [slope, yIntercept]

    def ListInterceptingSquares(self, point1, point2):
        """Return approximate cells crossed by a line of sight or projectile path.

        Positions are [x, y], while the backing map is indexed [y][x]. The
        explicit order below keeps shot paths correct on rectangular maps.
        """
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
                interceptingCells.append(self.map[y][i])
            return interceptingCells

        for i in range(min(point1[1], point2[1]), max(point1[1], point2[1]) + 1):
            x = round((i - intercept) / slope)
            interceptingCells.append(self.map[i][x])
        return interceptingCells

    def mapInit(self):
        """Build the world through the dedicated map-generation module."""
        from mechgame.world import MapGenerator
        self.map = MapGenerator(self.mapWidth, self.mapHeight).build(self)
