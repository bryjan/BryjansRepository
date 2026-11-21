"""Live mech entities, pilots, sensing, movement, and reporting."""

import copy
import math

from termcolor import colored

from . import effects
from .mechs import Cockpit
from . import radar

__all__ = ["Entity", "Pilot"]


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
        self.radarPower = self.mechClass.radarPower / (1 + (self.speed * .25))
        # Hull abilities can temporarily amplify both visual range and the
        # radar source projected by this individual mech.
        self.sensorBoostMultiplier = 1
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
        # Patrol speeds describe the distance this mech can repeat every turn
        # without draining its energy reserve. They deliberately use plain
        # ground for off-road travel so later AI can compare units cheaply.
        self.offRoadPatrolSpeed = 0
        self.roadPatrolSpeed = 0
        self.baseOffRoadPatrolSpeed = 0
        self.baseRoadPatrolSpeed = 0
        self.readinessMetrics = {}
        self.combatReadiness = 0
        self.combatReady = False
        self.needsResupply = False
        self.needsRepair = False
        self.needsRetreat = False
        self.lowEnergy = False
        self.mobilityImpaired = False
        self.canMaintainFormation = False
        self.hasUsableWeapon = False
        self.travelSpeed = 0
        self.needrest = False
        # Tactical memory is useful to both AI and the player fire menu.
        self.lastFiredAt = None
        self.directlyVisibleEnemies = []
        self.trackedEnemies = []
        # The right tactical panel keeps a selected enemy here. When empty or
        # stale, it automatically falls back to the nearest tracked contact.
        self.focusedEnemy = None

        # A destroyed cockpit takes the whole mech out of the current match.
        self.destroyed = False
        self.refreshReadiness()
        self.baseOffRoadPatrolSpeed = self.offRoadPatrolSpeed
        self.baseRoadPatrolSpeed = self.roadPatrolSpeed


    def __repr__(self):
        return self.pilot.name

    def roundRefresh(self, matchInfo):
        """Restore per-round state and refresh the mech's derived statistics."""

        #basic stats
        self.clearTurnAbilities()
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

        effects.apply_turn_start_effects(matchInfo, self)
        if self.destroyed:
            return

        #get visuals
        self.getVisuals(matchInfo)

        self.refreshReadiness(matchInfo)

    def clearTurnAbilities(self):
        """Remove temporary hull-ability effects as this mech begins a new turn."""
        self.sensorBoostMultiplier = 1
        self.visPower = int(self.mechClass.visPower)
        for weapon in self.mechClass.gunList:
            if weapon.turnDamageBonus:
                weapon.turnDamageBonus = 0
                weapon.updateWeaponStats()

    def _patrol_speed_for_cost(self, movement_cost):
        """Return sustainable tiles per turn after AP, MP, and energy limits."""
        action_limit = max(0, min(self.mechClass.apMax, self.mechClass.mpMax))
        if movement_cost <= 0:
            return action_limit
        return min(action_limit, max(0, self.mechClass.energyGen // movement_cost))

    def _patrol_cost(self, matchInfo, terrain_name, fallback_cost):
        """Read a terrain's current movement cost without requiring a match."""
        terrain = getattr(matchInfo, terrain_name, None) if matchInfo is not None else None
        if terrain is None:
            return fallback_cost
        return terrain.moveCost[self.size]

    def _ammo_readiness(self):
        """Return average finite-ammo readiness, treating unlimited arms as full."""
        ammunition = []
        for weapon in self.mechClass.gunList:
            if weapon.isMelee:
                ammunition.append(1)
            elif weapon.isLauncher:
                for ammo in weapon.ammoTypes:
                    if ammo.charges is None:
                        ammunition.append(1)
                    elif ammo.maxCharges:
                        ammunition.append(ammo.charges / ammo.maxCharges)
            elif weapon.charges is None:
                ammunition.append(1)
            elif weapon.maxCharges:
                ammunition.append(weapon.charges / weapon.maxCharges)
        return sum(ammunition) / len(ammunition) if ammunition else 1

    @staticmethod
    def _weapon_is_usable(weapon):
        """Return whether a mounted weapon can still make at least one attack."""
        if weapon.hp <= 0:
            return False
        if weapon.isMelee:
            return True
        if weapon.isLauncher:
            return any(ammo.charges is None or ammo.charges > 0 for ammo in weapon.ammoTypes)
        if weapon.charges is None:
            return True
        return weapon.charges > 0

    def refreshReadiness(self, matchInfo=None):
        """Recalculate AI-facing condition, supply, and sustained-travel flags.

        This does not choose an action. It gives future squad leaders a compact,
        stable picture of what each mech can safely contribute.
        """
        plains_cost = self._patrol_cost(matchInfo, "plains", 1)
        road_cost = self._patrol_cost(matchInfo, "road", 0)
        self.offRoadPatrolSpeed = self._patrol_speed_for_cost(plains_cost)
        self.roadPatrolSpeed = self._patrol_speed_for_cost(road_cost)
        self.travelSpeed = self.offRoadPatrolSpeed

        integrity = max(0, min(1, self.mechClass.condition / 100))
        ammo = self._ammo_readiness()
        energy = self.energy / self.mechClass.energyMax if self.mechClass.energyMax else 0
        operational_weapons = sum(
            self._weapon_is_usable(weapon) for weapon in self.mechClass.gunList
        )
        weapon_readiness = (
            operational_weapons / len(self.mechClass.gunList)
            if self.mechClass.gunList else 0
        )
        baseline_speed = self.baseRoadPatrolSpeed or self.roadPatrolSpeed
        mobility = self.roadPatrolSpeed / baseline_speed if baseline_speed else 0

        self.hasUsableWeapon = operational_weapons > 0
        self.lowEnergy = energy < 0.3
        self.needsResupply = ammo < 0.25
        self.needsRepair = integrity < 0.6 or self.cockpit.status < 2
        self.needsRetreat = integrity < 0.3 or self.cockpit.status < 1
        self.mobilityImpaired = mobility < 0.75
        self.canMaintainFormation = (
            not self.destroyed and self.roadPatrolSpeed > 0 and not self.mobilityImpaired
        )
        # Integrity is deliberately the strongest input: a well-armed mech
        # with a failing cockpit should not be sent into a prolonged fight.
        score = (
            integrity * 45
            + ammo * 20
            + energy * 15
            + mobility * 10
            + weapon_readiness * 10
        )
        self.combatReadiness = round(score)
        self.combatReady = (
            self.combatReadiness >= 60
            and self.hasUsableWeapon
            and not self.needsResupply
            and not self.needsRetreat
        )
        self.needrest = self.lowEnergy or self.needsRepair or not self.hasUsableWeapon
        self.readinessMetrics = {
            "integrity": round(integrity * 100),
            "ammo": round(ammo * 100),
            "energy": round(energy * 100),
            "mobility": round(mobility * 100),
            "weapons": round(weapon_readiness * 100),
            "score": self.combatReadiness,
        }



    def moveMech(self, matchInfo, input):
        """Attempt one keyboard-directed move and charge the required movement points."""
        map = matchInfo.map

        if self.ap == 0 or self.mp == 0 or self.energy == 0:
            print("You don't have the ability to move anymore this turn.")
            matchInfo.advTurn = False
            return

        match input:

            case "q":
                targetPos = [self.pos[0]-1, self.pos[1]+1]

            case "w":
                targetPos = [self.pos[0], self.pos[1]+1]

            case "e":
                targetPos = [self.pos[0]+1, self.pos[1]+1]

            case "a":
                targetPos = [self.pos[0]-1, self.pos[1]]

            case "s":
                targetPos = [self.pos[0], self.pos[1]-1]

            case "d":
                targetPos = [self.pos[0] + 1, self.pos[1]]

            case "z":
                targetPos = [self.pos[0] - 1, self.pos[1]-1]

            case "c":
                targetPos = [self.pos[0] + 1, self.pos[1]-1]

            case _:
                print("Not a valid movement input.")
                return

        targetX, targetY = targetPos
        if not (0 <= targetX < matchInfo.mapWidth and 0 <= targetY < matchInfo.mapHeight):
            print("That move would leave the map.")
            return

        # Rows are indexed by Y, then columns by X. Keeping this lookup in one
        # place prevents valid X positions on rectangular maps from being read
        # as row numbers.
        targetCell = map[targetY][targetX]
        moveCost = targetCell.terrain.moveCost[self.size]

        #checks for viability
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

        if self.flying:
            # Flight ignores terrain movement penalties but always costs at
            # least the mech's size in energy.
            moveCost = max(moveCost, self.size)

        can_cross_water = self.mechClass.canFloat or self.flying or self.size == 6
        if targetCell.terrain.requireFloat and not can_cross_water:
            print("Your mech can't travel over water.")
            return

        self.energy = int(self.energy - moveCost)
        self.ap -= 1
        self.mp = int(self.mp - 1)
        self.pos = list(targetPos)
        self.speed += 1
        effects.apply_entry_effects(matchInfo, self)
        self.refreshReadiness(matchInfo)
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

        # Keep fractional terrain losses so light effects such as desert heat
        # haze can matter, rather than being rounded away at every step.
        startingCell.visPower = self.visPower + startingCell.visualAbsorption

        calcList = [] #cells queued to be calced
        dontCalcList= [startingCell] #cells exempt from calcs
        for n in startingCell.nList:
            dontCalcList.append(n)
            if (
                0 < n.pos[0] < matchInfo.mapWidth
                and 0 < n.pos[1] < matchInfo.mapHeight
            ):
                calcList.append(n)

        for cell in calcList:
            dontCalcList.append(cell)
            closestNeighbor = cell.refClosestNeighborTo(startingCell.pos)
            visualLoss = closestNeighbor.visualAbsorption + round(math.dist(startingCell.pos, cell.pos), 0)
            cell.visPower = closestNeighbor.visPower - visualLoss

            if cell.visPower < 0:
                cell.visPower = 0

            if cell.visPower > 0:
                cell.canSee = True
                self.visibleCells.append(cell)
                for n in cell.nList:
                    if (n not in dontCalcList):
                        calcList.append(n)
                        dontCalcList.append(n)

        # A friendly scout flare acts as a temporary forward visual source.
        # Its cells become visible to this team without replacing the mech's
        # own sight calculation.
        self.visibleCells.extend(effects.scout_visible_cells(matchInfo, self.team))
        self.visibleCells = list(dict.fromkeys(self.visibleCells))
        self.team.share_vision(self, self.visibleCells)

        self.directlyVisibleEnemies = [
            entity
            for entity in matchInfo.entities
            if entity.team != self.team
            and matchInfo.map[entity.pos[1]][entity.pos[0]] in self.visibleCells
        ]
        radar.refresh_tracked_enemies(self)

    def getVisuals(self, matchInfo):
        """Update both visual and radar information for the current entity."""
        self.getVis(matchInfo)
        radar.refresh(matchInfo)


    def report(self, matchInfo, message, teamReport = False, critical = False):
        """Store one deduplicated squad report for later panel display."""
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
