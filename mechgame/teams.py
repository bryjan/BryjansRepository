"""Squad and team coordination, reporting, and map placement."""

import random
from dataclasses import dataclass

__all__ = ["MapVisibilityFlags", "Squad", "Team"]


MOVEMENT_MODES = {"patrol", "move", "double_time"}
MOVEMENT_BEHAVIORS = {"formation", "road_patrol"}


@dataclass
class MapVisibilityFlags:
    """Policy controls for a team's strategic-map fog of war."""

    # Explicitly retained as a debugging override; normal matches use fog.
    debug_reveal_all: bool = False
    show_all_terrain: bool = False
    show_all_objectives: bool = False
    remember_explored_terrain: bool = True
    show_friendly_entities: bool = True
    show_visual_enemies: bool = True
    show_radar_contacts: bool = True
    show_known_effects: bool = True


class Squad:
    """Ordered group of mechs that acts together and shares intelligence."""
    ROLE_CAPABILITY_THRESHOLD = 60
    COMBAT_EFFECTIVE_FORCE_RATIO = 0.40

    def __init__(self, squadName, squadList, squadRole, playerControlled = False):
        self.name = squadName
        self.mechList = squadList #in order of command
        self.squadLead = self.mechList[0] if self.mechList else None

        self.role = squadRole
        self.playerControlled = playerControlled
        # Movement policy is deliberately separate from formation behavior.
        # A leader/planner may, for example, order a road patrol at normal
        # speed or double time without changing the squad's assigned mission.
        self.movementMode = "move"
        self.movementBehavior = "formation"
        # Teams hand down matching objective records to AI squads only.
        self.currentGoal = None
        self.currentGoals = []
        self.goalHistory = []
        self.macroObjective = ""
        self.microObjective = ""
        self.Ammo = 0
        self.supplies = 0
        self.effectiveness = 100
        self.reportLog = []
        # Force values use the cross-class balance rule: a mech is worth
        # roughly three combat-ready mechs one size class below it.
        self.combatReadyCount = 0
        self.combatForce = 0
        self.baselineCombatForce = 0
        self.combatEffectiveness = 0
        self.combatEffective = False
        self.shouldLeaveBattlefield = False
        self.roleCapabilityFlags = {}
        self.canFulfillCurrentGoal = True
        # Active-radar contacts are shared by every mech in this squad.
        self.radarTrackedEnemies = []
        # TODO(ai-squad-leader): retain the assessed stance, route, formation,
        # and per-mech orders here after the planner is implemented.

        for mech in self.mechList:
            mech.squad = self
        self.refreshCombatForce()

    def roundRefresh(self, matchInfo):
        """Refresh every squad member at the beginning of its round."""
        matchInfo.clearVisuals()
        self.radarTrackedEnemies = []
        for entity in self.mechList:
            entity.roundRefresh(matchInfo)
        self.refreshCombatForce()

    @staticmethod
    def _combat_force_for_size(size):
        """Convert a size class into the shared three-to-one force scale."""
        return 3 ** (size - 2)

    def refreshCombatForce(self):
        """Refresh force, role capability, and battlefield-withdrawal flags."""
        # The leader may be destroyed or ejected between refreshes. Keeping
        # this invariant here means every caller sees a live leader or None.
        if self.squadLead not in self.mechList:
            self.squadLead = self.mechList[0] if self.mechList else None
        ready_mechs = [mech for mech in self.mechList if mech.combatReady]
        self.combatReadyCount = len(ready_mechs)
        self.combatForce = round(
            sum(
                self._combat_force_for_size(mech.size)
                * mech.mechClass.combatForceMultiplier
                for mech in ready_mechs
            ),
            2,
        )
        if self.baselineCombatForce == 0 and self.combatForce > 0:
            self.baselineCombatForce = self.combatForce
        self._refreshOperationalFlags()
        return self.combatForce

    def roleReadiness(self):
        """Return the best live readiness available for every role in the squad."""
        readiness = {}
        for mech in self.mechList:
            for role, score in mech.roleReadiness.items():
                readiness[role] = max(readiness.get(role, 0), score)
        return readiness

    def _refreshOperationalFlags(self):
        """Turn mech readiness into squad-level capability and retreat signals."""
        readiness = self.roleReadiness()
        self.roleCapabilityFlags = {
            role: score >= self.ROLE_CAPABILITY_THRESHOLD
            for role, score in readiness.items()
        }
        required_roles = getattr(self.currentGoal, "required_roles", ())
        self.canFulfillCurrentGoal = self.canFillRoles(required_roles)
        self.combatEffectiveness = round(
            (self.combatForce / self.baselineCombatForce) * 100,
            1,
        ) if self.baselineCombatForce else 0
        self.combatEffective = (
            self.combatReadyCount > 0
            and self.combatForce >= self.baselineCombatForce * self.COMBAT_EFFECTIVE_FORCE_RATIO
        )
        # This is advice for a future squad-leader action planner. It does not
        # remove units or move the squad until that planner is implemented.
        self.shouldLeaveBattlefield = not self.combatEffective

    def canFillRoles(self, required_roles):
        """Return whether the squad currently supplies every requested role."""
        return all(self.roleCapabilityFlags.get(role, False) for role in required_roles)

    def setMovementPolicy(self, mode=None, behavior=None):
        """Set validated movement reserve and formation behavior preferences."""
        if mode is not None:
            if mode not in MOVEMENT_MODES:
                raise ValueError(f"Unknown movement mode '{mode}'.")
            self.movementMode = mode
        if behavior is not None:
            if behavior not in MOVEMENT_BEHAVIORS:
                raise ValueError(f"Unknown movement behavior '{behavior}'.")
            self.movementBehavior = behavior

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

        # The squad panel needs a readiness signal, not a long inventory.
        # Average every weapon's readiness for each mech. Direct weapons with
        # unlimited charges are always fully ready; launchers instead use the
        # readiness of their selectable shell pools.
        ammoSummary = []
        for mech in self.mechList:
            ammoPercentages = []
            for weapon in mech.mechClass.gunList:
                if weapon.isLauncher:
                    for ammo in weapon.ammoTypes:
                        if ammo.charges is not None and ammo.maxCharges:
                            ammoPercentages.append(ammo.charges / ammo.maxCharges)
                    continue
                if weapon.charges is None:
                    ammoPercentages.append(1)
                elif weapon.maxCharges:
                    ammoPercentages.append(weapon.charges / weapon.maxCharges)
            averageAmmo = round((sum(ammoPercentages) / len(ammoPercentages)) * 100) if ammoPercentages else 100
            ammoSummary.append(f"{mech.pilot.display_name} {averageAmmo}%")
        ammunition = " | ".join(ammoSummary) if ammoSummary else "none"

        return "\n".join([
            f"{self.name} squad status",
            f"Average integrity: {round(averageIntegrity)}% | Damaged modules: {damagedModules}/{totalModules}",
            f"Ammo readiness: {ammunition}",
            f"Most damaged: {mostDamaged.pilot.display_name} — {mostDamaged.mechClass.name} ({round(mostDamaged.mechClass.condition)}%)",
        ])

    def rosterReport(self):
        """Return the current pilot, chassis, and map location for each mech."""
        if not self.mechList:
            return "Squad roster: no operational mechs."

        entries = ["Squad roster:"]
        for index, mech in enumerate(self.mechList, start=1):
            entries.append(
                f"'{index}' {mech.pilot.display_name} — {mech.mechClass.name} at {mech.pos}"
            )
        return "\n".join(entries)

    def squadView(self, matchInfo):
        for entity in self.mechList:
            entity.getVisuals(matchInfo)


    def calcEffectiveness(self):
        """Recalculate aggregate squad integrity from the live mech blueprints."""
        if not self.mechList:
            self.effectiveness = 0
            return
        status = 0
        for mech in self.mechList:
            status += mech.mechClass.condition

        self.effectiveness = (status/len(self.mechList))*100

    def spawnSquad(self, map, spawnPosition, rng=None):
        """Place every squad member on a unique, in-bounds passable cell."""
        rng = rng if rng is not None else random
        mapHeight = len(map)
        mapWidth = len(map[0])
        radius = 2

        while True:
            xMin = max(1, spawnPosition[0] - radius)
            xMax = min(mapWidth - 2, spawnPosition[0] + radius)
            yMin = max(1, spawnPosition[1] - radius)
            yMax = min(mapHeight - 2, spawnPosition[1] + radius)
            validSpawnLocations = [
                list(cell.pos)
                for row in map[yMin:yMax + 1]
                for cell in row[xMin:xMax + 1]
                if cell.terrain.passable and not cell.terrain.requireFloat
            ]
            if len(validSpawnLocations) >= len(self.mechList):
                break
            if xMin == 1 and xMax == mapWidth - 2 and yMin == 1 and yMax == mapHeight - 2:
                raise ValueError("Map has insufficient passable cells to spawn this squad.")
            radius += 1

        for mech in self.mechList:
            position = rng.choice(validSpawnLocations)
            mech.pos = position
            validSpawnLocations.remove(position)





class Team:
    """Collection of squads with a shared name, resources, and report log."""
    def __init__(self, teamName, squadsList, playerControlled = False):
        self.name = teamName
        self.squadsList = squadsList
        self.resources = 0
        self.reportLog = []
        self.playerControlled = playerControlled
        # MatchInfo assigns this after scenario terrain and objectives exist.
        # It is deliberately data-only until the team-planning layer arrives.
        self.currentGoal = None
        self.currentGoals = []
        self.goalHistory = []
        # Team memory persists across each squad's turn in this match round.
        # Keys are enemy entities; values hold the strongest radar reading.
        self.radarContacts = {}
        self.mapVisibility = MapVisibilityFlags()
        # Terrain knowledge persists for the match, while sharedVisibleTiles
        # is rebuilt from the currently contributing friendly observers.
        self.exploredTiles = set()
        self.sharedVisibleTiles = set()
        # TODO(ai-factions): store faction doctrine here (risk tolerance,
        # preferred terrain, radar discipline, and morale behavior) rather
        # than branching on team names inside a future planner.

        for squads in self.squadsList:
            # Keep the object reference: turn sequencing needs its squad list.
            squads.team = self
            for mech in squads.mechList:
                mech.team = self

    def clear_shared_vision(self):
        """Discard only current visual coverage, retaining explored terrain."""
        self.sharedVisibleTiles.clear()

    def share_vision(self, mech, cells):
        """Share one capable mech's visual cells with the full team map."""
        if not mech.mechClass.shareData:
            return
        positions = {tuple(cell.pos) for cell in cells}
        self.sharedVisibleTiles.update(positions)
        if self.mapVisibility.remember_explored_terrain:
            self.exploredTiles.update(positions)
