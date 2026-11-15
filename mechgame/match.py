"""Match-wide state and turn-independent board calculations."""

import math
import random

from . import artillery
from . import effects
from . import radar


class MatchInfo:
    """Mutable state shared by one running match."""

    def __init__(self, mapSize, windowSize, teams, mapParams, mapHeight=None, rng=None):
        # ``mapSize`` remains the width for compatibility with older callers.
        # Height defaults to width so existing square-map games still work.
        self.mapSize = mapSize
        self.mapWidth = mapSize
        self.mapHeight = mapSize if mapHeight is None else mapHeight
        # Keep the original square setting for compatibility while rendering
        # reads these independent dimensions for a rectangular tactical view.
        self.windowSize = windowSize
        self.windowWidth = windowSize
        self.windowHeight = windowSize
        self.teamList = teams #team0 are nuetral entities
        self.playerSquad = ""
        self.entities = []
        self.abandonedMechs = []
        self.destroyedMechs = []
        # Fired launcher shells resolve only after future squad-turn handoffs.
        self.pendingImpacts = []
        self.matchRound = 0
        self.pov = ""
        self.matchOver = False
        self.winner = None
        self.resultMessage = ""
        self.mapParamsList = mapParams
        # One source of randomness makes seeded matches reproducible in tests
        # and eventually suitable for replay or save-file support.
        self.rng = rng if rng is not None else random.Random()
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

    def operational_teams(self):
        """Return teams that still have at least one mech in the match."""
        return [
            team for team in self.teamList
            if any(squad.mechList for squad in team.squadsList)
        ]

    def _finish_if_decided(self):
        """Record the result once only one operational team remains."""
        survivors = self.operational_teams()
        if len(survivors) > 1:
            return False

        self.matchOver = True
        self.winner = survivors[0] if survivors else None
        self.resultMessage = (
            f"Match complete: {self.winner.name} wins."
            if self.winner is not None
            else "Match complete: no team has operational mechs remaining."
        )
        self.advTurn = False
        self.turnEnded = False
        return True

    def _turn_slots(self):
        """Return squads in deterministic team/squad order, including empty ones."""
        return [
            (team, squad)
            for team in self.teamList
            for squad in team.squadsList
        ]

    def _begin_new_round(self):
        """Advance match-round effects and expire round-limited team memory."""
        self.matchRound += 1
        effects.advance_effects(self)
        for team in self.teamList:
            team.radarContacts.clear()

    def _next_operational_slot(self, current_squad):
        """Find the next non-empty squad and whether that crosses a round."""
        turn_slots = self._turn_slots()
        current_index = next(
            index for index, (_, squad) in enumerate(turn_slots)
            if squad is current_squad
        )
        for offset in range(1, len(turn_slots) + 1):
            slot_index = (current_index + offset) % len(turn_slots)
            team, squad = turn_slots[slot_index]
            if squad.mechList:
                return team, squad, current_index + offset >= len(turn_slots)
        return None, None, False

    def nextSquadTurn(self):
        """Advance to the next operational squad or finish the match.

        Empty squads remain in the ordered slot list so turn order remains
        stable, but they are skipped when selecting the next active squad.
        """
        if self.matchOver:
            return False

        current_squad = self.pov.squad
        # A pulse is active only for the squad turn in which it was ordered.
        # Clear every squad member so changing the point of view cannot let a
        # previous pilot's pulse survive into the next squad turn.
        for mech in current_squad.mechList:
            mech.clearTurnAbilities()
            if mech.radarPulseActive:
                mech.radarOn = False
                mech.radarPulseActive = False

        if self._finish_if_decided():
            return False

        _, next_squad, wrapped_round = self._next_operational_slot(current_squad)

        # The earlier survivor check ensures this only happens for malformed
        # matches without any schedulable squad.
        if next_squad is None:
            self.matchOver = True
            self.resultMessage = "Match complete: no operational squad remains."
            return False

        if wrapped_round:
            self._begin_new_round()
            if self._finish_if_decided():
                return False
            # Fire and other round effects may have destroyed the squad that
            # was selected before effects advanced. Select again from the
            # stable slot order after those removals.
            _, next_squad, _ = self._next_operational_slot(current_squad)

        # Sensor information is rebuilt for the squad that is about to act.
        self.clearVisuals()
        self.pov = next_squad.mechList[0]
        self.pov.squad.roundRefresh(self)

        # Resolve shells only after the new squad has been selected.  This
        # makes impacts belong to the new turn and prevents fresh smoke or
        # fire from being immediately aged during a round-boundary refresh.
        artillery.advance_impacts(self)
        self.advTurn = False
        self.turnEnded = False
        return True

    def nextMechinTeam(self):
        """Cycle the point of view through the current squad without ending its turn."""
        if self.matchOver or not self.pov.squad.mechList:
            return
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
        affected_entities = [
            entity
            for entity in self.entities
            if math.dist(location, entity.pos) <= radius
        ]
        self._report_explosion(location, soundRange, affected_entities)
        for entity in affected_entities:

            # Larger explosions can strike more parts; large targets spread the
            # blast across more armor, while small targets are more exposed.
            parts_to_hit = max(1, min(len(entity.mechClass.limbList), 3 + size - entity.size))
            # Every fragment hit strips one armor point. Blast size changes
            # the number of limbs exposed, not the armor removed per limb.
            armor_damage = 1
            for limb in self.rng.sample(entity.mechClass.limbList, parts_to_hit):
                limb.damage(self, damage, "explosion", armorDamage=armor_damage)

        # TODO: explosions can later add fire, smoke, and terrain effects.

    def _report_explosion(self, location, soundRange, affected_entities):
        """Let nearby mechs report an impact they saw or heard.

        Mechs inside the blast report being struck rather than merely seeing
        it. Visual confirmation is urgent information, while hearing alone
        gives a useful ordinary warning without exposing the impact location.
        """
        affected_entities = set(affected_entities)
        for entity in self.entities:
            if entity in affected_entities:
                entity.report(
                    self, "I was caught in an explosion!",
                    teamReport=False, critical=True,
                )
                continue

            sees_impact = any(
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
        self.map = MapGenerator(self.mapWidth, self.mapHeight, self.rng).build(self)
