"""Squad and team coordination, reporting, and map placement."""

import random
from dataclasses import dataclass

__all__ = ["MapVisibilityFlags", "Squad", "Team"]


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
    def __init__(self, squadName, squadList, squadRole, playerControlled = False):
        self.name = squadName
        self.mechList = squadList #in order of command
        self.squadLead = self.mechList[0]

        self.role = squadRole
        self.playerControlled = playerControlled
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
        # Active-radar contacts are shared by every mech in this squad.
        self.radarTrackedEnemies = []

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
        """Recalculate the ready headcount and comparable combat-force value."""
        ready_mechs = [mech for mech in self.mechList if mech.combatReady]
        self.combatReadyCount = len(ready_mechs)
        self.combatForce = round(
            sum(self._combat_force_for_size(mech.size) for mech in ready_mechs),
            2,
        )
        return self.combatForce

    def roleReadiness(self):
        """Return the best live readiness available for every role in the squad."""
        readiness = {}
        for mech in self.mechList:
            for role, score in mech.roleReadiness.items():
                readiness[role] = max(readiness.get(role, 0), score)
        return readiness

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
            ammoSummary.append(f"{mech.pilot.name} {averageAmmo}%")
        ammunition = " | ".join(ammoSummary) if ammoSummary else "none"

        return "\n".join([
            f"{self.name} squad status",
            f"Average integrity: {round(averageIntegrity)}% | Damaged modules: {damagedModules}/{totalModules}",
            f"Ammo readiness: {ammunition}",
            f"Most damaged: {mostDamaged.pilot.name} — {mostDamaged.mechClass.name} ({round(mostDamaged.mechClass.condition)}%)",
        ])

    def rosterReport(self):
        """Return the current pilot, chassis, and map location for each mech."""
        if not self.mechList:
            return "Squad roster: no operational mechs."

        entries = ["Squad roster:"]
        for index, mech in enumerate(self.mechList, start=1):
            entries.append(
                f"'{index}' {mech.pilot.name} — {mech.mechClass.name} at {mech.pos}"
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
