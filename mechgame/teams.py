"""Squad and team coordination, reporting, and map placement."""

import random

__all__ = ["Squad", "Team"]


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
                # Launchers hold multiple independently counted shell types;
                # report each payload rather than the launcher's empty tube.
                if weapon.isLauncher:
                    for ammo in weapon.ammoTypes:
                        ammunition = ammoByWeapon.setdefault(
                            ammo.name,
                            {"current": 0, "maximum": 0, "unlimited": False},
                        )
                        if ammo.charges is None:
                            ammunition["unlimited"] = True
                        else:
                            ammunition["current"] += ammo.charges
                            ammunition["maximum"] += ammo.maxCharges
                    continue
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
        """Recalculate aggregate squad integrity from the live mech blueprints."""
        status = 0
        for mech in self.mechList:
            status += mech.mechClass.condition

        self.effectiveness = (status/len(self.mechList))*100

    def spawnSquad(self, map, spawnPosition):
        """Place every squad member on a unique, in-bounds passable cell."""
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
            position = random.choice(validSpawnLocations)
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
        # Team memory persists across each squad's turn in this match round.
        # Keys are enemy entities; values hold the strongest radar reading.
        self.radarContacts = {}

        for squads in self.squadsList:
            # Keep the object reference: turn sequencing needs its squad list.
            squads.team = self
            for mech in squads.mechList:
                mech.team = self
