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
    COMBAT_MEMORY_TURNS = 2

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

        self.name = self.pilot.display_name
        self.squad = ""
        self.team = ""

        self.pos = [0,0] #[x,y]
        self.size = self.mechClass.size
        self.sizeStr = self.mechClass.sizeStr
        self.speed = 0 #tiles moved this turn
        self.movementBurstMode = None
        self.ap = int(self.mechClass.apMax)
        self.mp = int(self.mechClass.mpMax)
        self.energy = int(self.mechClass.energyMax)
        self.visPower = self.mechClass.visPower
        self.radarPower = self.mechClass.radarPower / (1 + (self.speed * .25))
        # Hull abilities can temporarily amplify both visual range and the
        # radar source projected by this individual mech.
        self.sensorBoostMultiplier = 1
        self.aiDashUsedThisTurn = False
        # Active radar starts silent.  The pilot can enable continuous scans or
        # spend energy on a single-turn pulse.
        self.radarOn = False
        self.radarPulseActive = False
        # TODO(ai-threat): replace this temporary switch with a shared,
        # visibility-limited threat assessment. It retains concrete signals
        # for two of this mech's turns so ejection and patrols model recent
        # combat without reading hidden units.
        self.inCombat = False
        self.combatQuietTurns = 0
        self.explosionAlert = False
        self.turnsStarted = 0
        self.lastCombatSignal = ""
        self.unknownEvadeSerial = 0
        # Traits and skills can later alter this leader-facing uncertainty.
        self.combatAssessmentError = .25

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
        self.hasArtillery = False
        self.roleReadiness = {}
        self.hasAvailableRole = True
        self.shouldFlee = False
        self.travelSpeed = 0
        self.needrest = False
        # Tactical memory is useful to both AI and the player fire menu.
        self.lastFiredAt = None
        self.directlyVisibleEnemies = []
        self.trackedEnemies = []
        # The right tactical panel keeps a selected enemy here. When empty or
        # stale, it automatically falls back to the nearest tracked contact.
        self.focusedEnemy = None
        # AI preserves this short-lived intent between its combat choice and
        # movement pass when closing distance would unlock better damage.
        self.approachTarget = None
        self.approachWeapon = None
        # TODO(ai-orders): future individual orders should live here only for
        # the current squad turn. The planner must not persist stale targets
        # after radar/visual contacts expire.

        # A destroyed cockpit takes the whole mech out of the current match.
        self.destroyed = False
        self.ejected = False
        self.fled = False
        self.refreshReadiness()
        self.baseOffRoadPatrolSpeed = self.offRoadPatrolSpeed
        self.baseRoadPatrolSpeed = self.roadPatrolSpeed


    def __repr__(self):
        return self.pilot.display_name

    def noteCombat(self, signal):
        """Record one observed or experienced combat signal for this mech."""
        if self.destroyed or self.ejected:
            return
        self.inCombat = True
        self.combatQuietTurns = 0
        self.lastCombatSignal = signal

    def _advanceCombatMemory(self):
        """Expire combat state after two of this mech's quiet turns."""
        if not self.inCombat:
            return
        self.combatQuietTurns += 1
        if self.combatQuietTurns >= self.COMBAT_MEMORY_TURNS:
            self.inCombat = False
            self.explosionAlert = False
            self.combatQuietTurns = 0
            self.lastCombatSignal = ""

    def roundRefresh(self, matchInfo):
        """Restore per-round state and refresh the mech's derived statistics."""

        #basic stats
        self.turnsStarted += 1
        self._advanceCombatMemory()
        self.clearTurnAbilities()
        self.turnStartPos = list(self.pos)
        self.speed = 0
        self.movementBurstMode = None

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
        self.aiDashUsedThisTurn = False
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
    def _weapons_ammo_readiness(weapons):
        """Return supply readiness for one role's relevant weapon set."""
        ammunition = []
        for weapon in weapons:
            if weapon.isMelee or weapon.charges is None and not weapon.isLauncher:
                ammunition.append(1)
            elif weapon.isLauncher:
                ammunition.extend(
                    1 if ammo.charges is None else ammo.charges / ammo.maxCharges
                    for ammo in weapon.ammoTypes
                    if ammo.maxCharges
                )
            elif weapon.maxCharges:
                ammunition.append(weapon.charges / weapon.maxCharges)
        return sum(ammunition) / len(ammunition) if ammunition else 0

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

    def _role_readiness(self, role, integrity, energy, mobility, weapon_readiness):
        """Score one stated role without forcing it through combat readiness."""
        # A sensor/scout needs its active array as well as an intact helm.
        # Visual-only spotting remains useful to combat roles, but does not
        # make a dedicated sensor fulfill its specialist role.
        sensor_operational = self.mechClass.helm.hp > 0 and self.mechClass.radarPower > 0
        artillery_weapons = [
            weapon for weapon in self.mechClass.gunList if weapon.isLauncher
        ]
        artillery_ammo = self._weapons_ammo_readiness(artillery_weapons)
        artillery_operational = any(
            self._weapon_is_usable(weapon) for weapon in artillery_weapons
        )

        if role in ("sensor", "scout"):
            # Sensors remain valuable for a team even after their sidearm is
            # empty, so their score intentionally ignores weapon ammunition.
            score = integrity * 40 + energy * 25 + mobility * 20 + (15 if sensor_operational else 0)
            return round(score) if sensor_operational else 0
        if role in ("artillery", "fire_support", "long_range_fire_support"):
            if not artillery_operational:
                return 0
            return round(integrity * 35 + artillery_ammo * 35 + energy * 15 + mobility * 15)
        if role == "skirmisher":
            if not self.hasUsableWeapon:
                return 0
            return round(
                integrity * 25 + weapon_readiness * 25 + energy * 20 + mobility * 30
            )
        if role in ("front_line", "anchor", "assault", "combat"):
            return self.combatReadiness if self.hasUsableWeapon else 0
        # New content can declare a role before it has bespoke logic; it gets
        # the general combat score rather than disappearing from AI planning.
        return self.combatReadiness if self.hasUsableWeapon else 0

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

        thresholds = self.mechClass.readinessProfile
        self.hasUsableWeapon = operational_weapons > 0
        self.hasArtillery = any(weapon.isLauncher for weapon in self.mechClass.gunList)
        self.lowEnergy = energy < thresholds.get("low_energy", 0.3)
        self.needsResupply = ammo < thresholds.get("resupply_ammo", 0.25)
        self.needsRepair = (
            integrity < thresholds.get("repair_integrity", 0.6)
            or self.cockpit.status < 2
        )
        self.needsRetreat = (
            integrity < thresholds.get("retreat_integrity", 0.3)
            or self.cockpit.status < 1
        )
        self.mobilityImpaired = mobility < thresholds.get("mobility_ratio", 0.75)
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
            self.combatReadiness >= thresholds.get("combat_ready", 60)
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
        self.roleReadiness = {
            role: self._role_readiness(role, integrity, energy, mobility, weapon_readiness)
            for role in self.mechClass.roles
        }
        role_threshold = getattr(self.squad, "ROLE_CAPABILITY_THRESHOLD", 60)
        self.hasAvailableRole = any(
            score >= role_threshold for score in self.roleReadiness.values()
        )
        # Supplies are intentionally a simple team-wide reserve for now. A
        # depleted specialist stays in the field only when a future resupply
        # or repair action could restore its role.
        team_supplies = getattr(self.team, "supplies", 0)
        recoverable = team_supplies > 0 and (self.needsResupply or self.needsRepair)
        self.shouldFlee = not self.destroyed and not self.ejected and not (
            self.hasAvailableRole or recoverable
        )
        if hasattr(self.squad, "refreshCombatForce"):
            self.squad.refreshCombatForce()



    _DIRECTION_OFFSETS = {
        "q": (-1, 1), "w": (0, 1), "e": (1, 1), "a": (-1, 0),
        "s": (0, -1), "d": (1, 0), "z": (-1, -1), "c": (1, -1),
    }

    def moveCostTo(self, matchInfo, targetPos):
        """Return a legal adjacent step's energy cost, or its failure reason.

        Both player input and the AI call this validation path. A string reason
        makes callers free to present an error or silently consider another
        route without duplicating terrain and occupancy rules.
        """
        targetX, targetY = targetPos
        if self.ap <= 0 or self.mp <= 0:
            return None, "No action or movement points remain."
        if max(abs(targetX - self.pos[0]), abs(targetY - self.pos[1])) != 1:
            return None, "Movement must be one adjacent tile."
        if not (0 <= targetX < matchInfo.mapWidth and 0 <= targetY < matchInfo.mapHeight):
            return None, "That move would leave the map."

        targetCell = matchInfo.map[targetY][targetX]
        is_exit_tile = targetCell.terrain is matchInfo.border
        if not targetCell.terrain.passable and not is_exit_tile:
            return None, "This cell's terrain is impassable."
        if any(entity is not self and entity.pos == [targetX, targetY] for entity in matchInfo.entities):
            return None, "Something is in your way."

        can_cross_water = self.mechClass.canFloat or self.flying or self.size == 6
        if targetCell.terrain.requireFloat and not can_cross_water:
            return None, "Your mech can't travel over water."

        # Borders are normally impassable scenery, except when a mech is
        # deliberately walking onto one to leave the battlefield.
        moveCost = 1 if is_exit_tile else targetCell.terrain.moveCost[self.size]
        if self.flying:
            # Flight ignores terrain penalties but retains a size-based cost.
            moveCost = max(moveCost, self.size)
        if self.energy < moveCost:
            return None, (
                f"You don't have enough energy to travel over {targetCell.terrain.name}; "
                f"you need {moveCost}."
            )
        return moveCost, None

    def moveTo(self, matchInfo, targetPos, announce=True):
        """Move one legal step to a coordinate and return whether it succeeded."""
        moveCost, reason = self.moveCostTo(matchInfo, targetPos)
        if reason is not None:
            if announce:
                print(reason)
            return False

        if hasattr(self.squad, "movementMode"):
            from .ai import _energy_ceiling
            if self.energy >= _energy_ceiling(self, self.squad.movementMode):
                self.movementBurstMode = self.squad.movementMode
        self.energy = int(self.energy - moveCost)
        self.ap -= 1
        self.mp = int(self.mp - 1)
        self.pos = list(targetPos)
        if matchInfo.raidObjective is not None:
            matchInfo.raidObjective.moved(self)
        self.speed += 1
        effects.apply_entry_effects(matchInfo, self)
        self.refreshReadiness(matchInfo)
        matchInfo.advTurn = True
        if getattr(self.squad, "autoTravelEnabled", False) and self.squad.playerControlled:
            from .travel import follow, warnings
            if self is self.squad.squadLead and not self.destroyed:
                follow(matchInfo, self.squad)
            else:
                warnings(matchInfo, self.squad)
        return True

    def moveMech(self, matchInfo, direction):
        """Translate a player direction key into the shared one-step action."""
        offset = self._DIRECTION_OFFSETS.get(direction)
        if offset is None:
            print("Not a valid movement input.")
            return False
        targetPos = [self.pos[0] + offset[0], self.pos[1] + offset[1]]
        return self.moveTo(matchInfo, targetPos)

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
        if self.directlyVisibleEnemies:
            self.noteCombat("enemy in visual range")
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
        report = f"{critMessage}Round: {matchRound} |  {self.pilot.display_name}: {message}"
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
            self.squad.refreshCombatForce()
        if self not in matchInfo.destroyedMechs:
            matchInfo.destroyedMechs.append(self)
        self.team.ensureManualControl()

        # A destroyed active mech cannot continue taking actions this turn.
        if matchInfo.pov is self:
            matchInfo.turnEnded = True

    def ejectionOdds(self, matchInfo):
        """Return current RTB/Evading/Captured odds before pilot skills apply."""
        odds = {"RTB": 25, "Evading": 50, "Captured": 25} if self.inCombat else {
            "RTB": 55, "Evading": 40, "Captured": 5,
        }
        friendly_nearby = any(
            entity is not self
            and entity.team is self.team
            and math.dist(entity.pos, self.pos) <= 6
            for entity in matchInfo.entities
        )
        enemy_nearby = any(
            entity.team is not self.team
            and math.dist(entity.pos, self.pos) <= 8
            for entity in matchInfo.entities
        )
        terrain_name = matchInfo.map[self.pos[1]][self.pos[0]].terrain.name
        if friendly_nearby:
            odds["RTB"] += 15
            odds["Evading"] -= 10
            odds["Captured"] -= 5
        if enemy_nearby:
            odds["RTB"] -= 10
            odds["Captured"] += 10
        if terrain_name in {"road", "tunnel", "urban center", "suburbs"}:
            odds["RTB"] += 5
            odds["Evading"] -= 5
        elif terrain_name in {"forest", "mountain"}:
            odds["RTB"] -= 5
            odds["Evading"] += 5
        return odds

    def eject(self, matchInfo):
        """Abandon this mech and resolve its pilot's immediate survival state."""
        if self.destroyed or self.ejected:
            print("This mech can no longer eject.")
            return False

        odds = self.ejectionOdds(matchInfo)
        roll = matchInfo.rng.randint(1, 100)
        if roll <= odds["RTB"]:
            outcome = "RTB"
            self.pilot.status = "RTB"
            self.pilot.returned = True
        elif roll <= odds["RTB"] + odds["Evading"]:
            outcome = "Evading"
            self.pilot.status = "Evading"
        else:
            outcome = "Captured"
            self.pilot.status = "MIA"

        self.ejected = True
        self.pilot.ejectionOutcome = outcome
        self.pilot.ejectionLocation = tuple(self.pos)
        self.report(matchInfo, f"Ejected from mech: {outcome}.", critical=True)
        if self in matchInfo.entities:
            matchInfo.entities.remove(self)
        if self.squad and self in self.squad.mechList:
            self.squad.mechList.remove(self)
            if self.squad.squadLead is self and self.squad.mechList:
                self.squad.squadLead = self.squad.mechList[0]
            self.squad.refreshCombatForce()
        if self not in matchInfo.abandonedMechs:
            matchInfo.abandonedMechs.append(self)
        if self.pilot not in matchInfo.ejectedPilots:
            matchInfo.ejectedPilots.append(self.pilot)
        self.team.ensureManualControl()
        if matchInfo.pov is self:
            matchInfo.turnEnded = True
        return True

    def flee(self, matchInfo):
        """Leave from a border tile, preserving this mech and its pilot."""
        if self.destroyed or self.ejected or self.fled:
            print("This mech can no longer flee.")
            return False
        if not (
            self.pos[0] in (0, matchInfo.mapWidth - 1)
            or self.pos[1] in (0, matchInfo.mapHeight - 1)
        ):
            print("A mech must reach a border tile before it can flee.")
            return False

        self.fled = True
        self.pilot.status = "RTB"
        self.pilot.returned = True
        self.report(matchInfo, "Fled the battlefield with mech intact.", critical=True)
        if self in matchInfo.entities:
            matchInfo.entities.remove(self)
        if self.squad and self in self.squad.mechList:
            self.squad.mechList.remove(self)
            if self.squad.squadLead is self and self.squad.mechList:
                self.squad.squadLead = self.squad.mechList[0]
            self.squad.refreshCombatForce()
        if self not in matchInfo.fledMechs:
            matchInfo.fledMechs.append(self)
        self.team.ensureManualControl()
        if matchInfo.pov is self:
            matchInfo.turnEnded = True
        return True


class Pilot: #TODO add pilot levels, skills, certs
    """Named crew member assigned to an entity."""
    NICKNAME_DISPLAY_LIMIT = 16
    def __init__(self, name, nickname=None, callsign=None):
        self.name = self._clean_identity(name, "name")
        self.nickname = self._clean_identity(nickname, "nickname", allow_empty=True)
        self.nicknameVisible = True
        self.callsign = self._clean_identity(callsign, "callsign", allow_empty=True)
        self.status = "Active"
        self.returned = False
        self.ejectionOutcome = None
        self.ejectionLocation = None
        # Persistent campaigns can safely begin recording progression now.
        # Empty defaults keep ordinary skirmish pilots lightweight and ensure
        # older saves can be upgraded without inventing a trait or skill.
        self.traits = []
        self.skills = {}

    @staticmethod
    def _clean_identity(value, label, allow_empty=False):
        """Normalize an identity value and make accidental blank names clear."""
        if value is None and allow_empty:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            if allow_empty:
                return None
            raise ValueError(f"Pilot {label} cannot be blank.")
        return cleaned

    @property
    def display_name(self):
        """Return callsign or a length-aware nickname before the legal name."""
        if self.callsign:
            return self.callsign
        if not self.nickname or not self.nicknameVisible:
            return self.name
        first_name = self.name.split()[0]
        combined = f'{first_name} "{self.nickname}"'
        return combined if len(combined) <= self.NICKNAME_DISPLAY_LIMIT else f'"{self.nickname}"'

    def assign_name(self, name):
        """Set the pilot's permanent legal name used for campaign identity."""
        self.name = self._clean_identity(name, "name")

    def assign_nickname(self, nickname):
        """Set or clear an earned secondary display name for future progression."""
        self.nickname = self._clean_identity(nickname, "nickname", allow_empty=True)

    def toggle_nickname_visibility(self):
        """Show or hide an earned nickname without changing the stored reward."""
        self.nicknameVisible = not self.nicknameVisible
        return self.nicknameVisible

    def assign_callsign(self, callsign):
        """Set or clear the player-assigned callsign with display priority."""
        self.callsign = self._clean_identity(callsign, "callsign", allow_empty=True)

    def kill(self, matchInfo):
        """Record a fatal cockpit loss without treating it as an ejection."""
        self.status = "KIA"
        self.returned = False
        if self not in matchInfo.killedPilots:
            matchInfo.killedPilots.append(self)
