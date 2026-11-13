"""Mech blueprints, damageable parts, weapons, and installed modules."""

import copy
import math
import random

from . import artillery

__all__ = ["Cockpit", "Helm", "Hull", "Legs", "MechClass", "MechPart", "Module", "WeaponLimb"]


class MechClass: #a constructed mech not a npc or player
    """Reusable mech blueprint composed from hull, helm, legs, and weapon limbs."""
    def __init__(self, name, symbol, color, mechHull, mechHelm, mechLeg, limblist = [], description = ""):

        #basic details
        self.name = name
        self.symbol = symbol
        self.color = color
        self.mech = ""

        #limb objects
        self.hull = copy.deepcopy(mechHull)
        self.helm = copy.deepcopy(mechHelm)
        self.legs = copy.deepcopy(mechLeg)
        #limbs roughly organized by height off ground
        self.limbList = [self.legs, self.hull]
        self.gunList = []
        for limb in limblist:
            self.limbList.append(copy.deepcopy(limb))
        self.limbList.append(self.helm)

        for limb in self.limbList:
            limb.mechClass = self
            if limb.isGun == True:
                self.gunList.append(limb)
        if len(self.gunList) == 1:
            self.gunList[0].defaultGun = True

        #initialize limb passed stats
        self.limbsConditionList = []
        self.size = 0
        self.radarSig = 0
        self.apMax = 0
        self.mpMax = 0
        self.energyMax = 0
        self.energyGen = 0
        self.shareData = False
        self.visPower = 0
        self.radarPower = 0
        self.radarEnergyCost = 0
        self.passiveRadar = False
        self.canfloat = False
        self.canFly = False
        self.initFlying = False

        self.passedStatsList = ["size","radarSig","apMax","mpMax","energyMax","energyGen","shareData","visPower","radarPower","radarEnergyCost","passiveRadar","canFly","canFloat","initFlying"]

        self.statUpdate()

        self.condition = sum(self.limbsConditionList) / len(self.limbsConditionList) * 100
        self.sizeStrList = ["flat", "tiny", "small", "medium", "large", "huge", "titanic"]
        self.sizeStr = self.sizeStrList[self.size]

        self.desc = description

    def displayStats(self): #basic stats display for bug fixing. TODO redo to look nicer and adding descriptions for gameplay
        pass

    def statUpdate(self):
        """Recalculate derived mech statistics after a part or module changes."""
        #retrieve limb passed stats
        for limb in self.limbList:
            limb.updateModules()
            self.limbsConditionList.append(limb.limbCon)
            for stat in self.passedStatsList:
                if getattr(limb, stat, "No attribute of that Name") != "No attribute of that Name":
                    setattr(self, stat, getattr(limb, stat))


    def statReset(self): #TODO resets mech's stats to default, including its limbs and modules
        pass

    def roundRefresh(self): #TODO refreshes round based stats(AP,MP,moved)and adds round based resources ex.power from powerGen
        """Restore action and movement resources for a new round."""
        pass


class MechPart: # super class to mech limbs
    """Base component with armor, hit points, modules, and derived modifiers."""
    def __init__ (self, name, armor, hp, moduleList, desc = ""):

        self.desc = desc
        self.name = name
        self.mechClass = "" #will be assigned when attached to a mech
        self.isGun = False

        self.modsList = copy.deepcopy(moduleList)

        #limb stats
        self.baseArmor = armor
        self.bonusArmor = 0
        self.multiArmor = 1
        self.armor = (self.baseArmor * self.multiArmor) + self.bonusArmor
        self.startingArmor = int(self.armor)
        self.armorCon = self.armor / self.startingArmor

        self.baseHP = hp
        self.bonusHP = 0
        self.multiHP = 1
        self.hp = (self.baseHP * self.multiHP) + self.bonusHP
        self.startingHP = int(self.hp)
        self.hpCon = self.hp / self.startingHP

        self.limbCon = round((self.armorCon * .25) + (self.hpCon * .75), 2)
        self.updateModules()

    def updateModules(self):
        """Apply this part's active module modifiers to its target attributes.

        Module stat arrays are indexed by module condition: destroyed (0),
        damaged (1), then intact (2).
        """
        for m in self.modsList:
            if m.modType == 1: #skips modules that make no stat change
                i = 0
                while i < len(m.statNames):
                    if getattr(self, m.statNames[i], "x") == "x":
                        #print(m.name + " is incompatable with " + self.name)
                        #print(self.name + " has no " + m.statNames[i])
                        return
                    else:
                        setattr(self, m.statNames[i], m.statsArray[i][m.status])
                        #print("updated " + m.name + " " + m.statNames[i] + " to " + str(m.statsArray[i][m.status]))
                    i += 1
        self.updateStats()

    def updateStats(self):

        if getattr(self, "isGun", False) != False:
            self.updateWeaponStats()

        if getattr(self, "isLauncher", False) != False:
            self.updateLauncherStats()

        if getattr(self, "size", False) != False:
            self.updateHullStats()

        if getattr(self, "apMax", False) != False:
            self.updateHelmStats()

        if getattr(self, "mpMax", False) != False:
            self.updateLegStats()



    def damage(self, matchInfo, dmgAmount, damageSource, armorPiercing = False, armorDamage = 0, ):
        """Resolve damage and return whether it penetrated armor into hit points."""

        #no negative damage values
        dmg = dmgAmount
        if dmgAmount < 0:
            dmg = 0

        armorDmg = armorDamage
        if armorDamage < 0:
            armorDmg = 0

        #damage source string for damage report
        dmgSource = f"" + damageSource

        #damage calc
        if armorPiercing == False:
            dmg = dmg - self.armor
            if dmg <= 0:
                return False
        else:
            dmg = round(dmg - (self.armor / 4))
            if dmg <= 0:
                return False

        #applying damage
        self.hp -= dmg
        if self.hp < 0:
            self.hp = 0

        self.armor -= armorDmg
        if self.armor < 0:
            self.armor = 0

        #determining if a module was damaged / crit
        if random.randint(0, self.hp) + dmgAmount > self.hp + self.armor:
            self.critical(matchInfo)

        #updating limb's condition
        self.updateStats()
        self.armorCon = self.armor / self.startingArmor
        self.hpCon = self.hp / self.startingHP
        self.limbCon = round((self.armorCon * .25) + (self.hpCon * .75), 2)
        self.mechClass.limbsConditionList = []
        for limb in self.mechClass.limbList:
            self.mechClass.limbsConditionList.append(limb.limbCon)
        self.mechClass.condition = round(sum(self.mechClass.limbsConditionList) / len(self.mechClass.limbList) * 100)

        #reporting damage
        self.mech.report(
            matchInfo, "I was hit by a " + dmgSource + "!",
            teamReport=False, critical=(damageSource == "fire"),
        )
        return True

    def critical (self, matchInfo):
        #checking if there is modules to damage
        if len(self.modsList) == 0:
            return
        totalStatus = 0
        for mod in self.modsList:
            totalStatus += mod.status
        if totalStatus == 0:
            return

        #picking random module from limb
        dmgdMod = random.choice(self.modsList)
        while dmgdMod.status == 0:
            dmgdMod = random.choice(self.modsList)

        self.mech.report(matchInfo, dmgdMod.name + " was damaged!", teamReport = False, critical = False)
        dmgdMod.damage(matchInfo)
        self.mechClass.statUpdate()
        # Damaged modules can lower live resource limits immediately. Clamp the
        # current values so a mech cannot keep capacity or movement it lost.
        self.mech.energy = min(self.mech.energy, self.mechClass.energyMax)
        self.mech.mp = min(self.mech.mp, self.mechClass.mpMax)


class Legs(MechPart): #subclass mechpart
    """Mech part that contributes mobility and optional floating or flight."""
    def __init__ (self, name, armor, hp, moduleList, speed, float = False, fly = False, desc = ""): #this will initi the superclass the same sats
        super().__init__(name, armor, hp, moduleList, desc="")

        self.baseMP = speed
        self.bonusMP = 0
        self.multiMP = 1
        self.mpMax = (self.baseMP * self.multiMP) + self.bonusMP

        self.canFloat = float
        self.canFly = fly
        self.initFly = fly

    def updateLegStats(self):
        self.mpMax = int((self.baseMP * self.multiMP) + self.bonusMP)

class Hull(MechPart):
    """Mech part that supplies power, signature, and chassis size."""
    def __init__ (self, name, armor, hp, moduleList, pwrCapacity, pwrGen, radarSig, size, desc = ""):
        super().__init__(name, armor, hp, moduleList, desc = "")

        self.size = size

        self.baseRadarSig = radarSig
        self.bonusRadarSig = 0
        self.multiRadarSig = 1
        self.radarSig = (self.baseRadarSig * self.multiRadarSig) + self.bonusRadarSig

        self.baseEnergy = pwrCapacity
        self.bonusEnergy = 0
        self.multiEnergy = 1
        self.energyMax = (self.baseEnergy * self.multiEnergy) + self.bonusEnergy

        self.baseEnergyGen = pwrGen
        self.bonusEnergyGen = 0
        self.multiEnergyGen = 1
        self.energyGen = (self.baseEnergyGen * self.multiEnergyGen) + self.bonusEnergyGen

    def updateHullStats(self):
        self.radarSig = int((self.baseRadarSig * self.multiRadarSig) + self.bonusRadarSig)
        self.energyMax = int((self.baseEnergy * self.multiEnergy) + self.bonusEnergy)
        self.energyGen = int((self.baseEnergyGen * self.multiEnergyGen) + self.bonusEnergyGen)


class Helm(MechPart):
    """Mech part that supplies action points and sensor power."""
    def __init__ (self, name, armor, hp, moduleList, ap, visualPower, radarPower, radarEnergyCost=0, desc=""):
        super().__init__(name, armor, hp, moduleList, desc="")
        self.baseAP = ap
        self.bonusAP = 0
        self.multiAP = 1
        self.apMax = (self.baseAP * self.multiAP) + self.bonusAP

        self.baseVisPower = visualPower
        self.bonusVisPower = 0
        self.multiVisPower = 1
        self.visPower = (self.baseVisPower * self.multiVisPower) + self.bonusVisPower

        self.baseRadarPower = radarPower
        self.bonusRadarPower = 0
        self.multiRadarPower = 1
        self.radarPower = (self.baseRadarPower * self.multiRadarPower) + self.bonusRadarPower

        self.baseRadarEnergyCost = radarEnergyCost
        self.bonusRadarEnergyCost = 0
        self.multiRadarEnergyCost = 1
        self.radarEnergyCost = (self.baseRadarEnergyCost * self.multiRadarEnergyCost) + self.bonusRadarEnergyCost

        self.shareData = True
        self.passiveRadar = False

    def updateHelmStats(self):
        self.apMax = int((self.baseAP * self.multiAP) + self.bonusAP)
        self.visPower = int((self.baseVisPower * self.multiVisPower) + self.bonusVisPower)
        self.radarPower = int((self.baseRadarPower * self.multiRadarPower) + self.bonusRadarPower)
        self.radarEnergyCost = int((self.baseRadarEnergyCost * self.multiRadarEnergyCost) + self.bonusRadarEnergyCost)


class WeaponLimb(MechPart):
    """Arm-mounted weapon with ammunition, costs, accuracy, and damage stats.

    A launcher draws its profiles from selectable ammunition. Each ammunition
    type supplies three range-band arrays:
    ``[max_range, scatter_tiles, turns_to_land, optional_damage_falloff]``.
    Direct weapons leave ``ammoTypes`` as ``None`` and resolve at once.
    """
    def __init__ (self, name, armor, hp, moduleList, damage, accuracy, soundRep, charges, projectileCount = 1, apCost = 1, energyCost = 0, speedPenalty = 8, armorPiercing = False, armorDamage = 0, maxRange = None, desc = "", launcherRanges = None, blastRadius = 0, blastSize = 0, ammoTypes = None):
        super().__init__(name, armor, hp, moduleList, desc = "")

        self.desc = desc
        self.isGun = True
        self.defaultGun = False

        self.baseProjectileCount = projectileCount
        self.bonusProjectileCount = 0
        self.multiProjectileCount = 1
        self.projectileCount = (self.baseProjectileCount * self.multiProjectileCount) + self.bonusProjectileCount

        self.baseDmg = damage
        self.bonusDmg = 0
        self.multiDmg = 1
        self.dmg = (self.baseDmg * self.multiDmg) + self.bonusDmg


        self.baseAccuracy = accuracy #affected by visAbsorb of tiles, higher means more accuracy
        self.bonusAccuracy = 0
        self.multiAccuracy = 1
        self.accuracy = (self.baseAccuracy * self.multiAccuracy) + self.bonusAccuracy

        self.baseSoundReport = soundRep #the distance the weapon can be heard from
        self.bonusSoundReport = 0
        self.multiSoundReport = 1
        self.soundReport = (self.baseSoundReport * self.multiSoundReport) + self.bonusSoundReport

        self.maxCharges = charges
        self.charges = charges #amount of ammo carried

        self.apCost = apCost
        self.energyCost = energyCost

        self.speedPenalty = speedPenalty

        self.piercing = armorPiercing

        self.armorDamage = armorDamage

        # Any accuracy-affecting module may change this multiplier. The
        # Holosight is only one example of such a module.
        self.accuracyMultiplier = 1
        self.maxRange = maxRange
        self.blastRadius = blastRadius
        self.blastSize = blastSize
        self.ammoTypes = copy.deepcopy(ammoTypes) if ammoTypes else []
        # Accept the previous launcher argument while normalizing it into one
        # selectable standard shell. New content should pass ``ammoTypes``.
        if launcherRanges is not None and not self.ammoTypes:
            self.ammoTypes.append(artillery.LauncherAmmo(
                "Standard Shell", launcherRanges, charges=charges,
                blastRadius=blastRadius, blastSize=blastSize,
            ))
        self.selectedAmmoIndex = 0
        self.isLauncher = bool(self.ammoTypes)

    def updateWeaponStats(self):
        self.projectileCount = int((self.baseProjectileCount * self.multiProjectileCount) + self.bonusProjectileCount)
        self.accuracy = int((self.baseAccuracy * self.multiAccuracy) + self.bonusAccuracy)
        self.soundReport = int((self.baseSoundReport * self.multiSoundReport) + self.bonusSoundReport)

    def updateLauncherStats(self):
        """Reserve a dedicated update hook for future launcher-only modules."""

    def emitSound(self, matchInfo):
        """Send a launch or gunfire report to enemies within audible range."""
        shooter = matchInfo.pov
        for entity in matchInfo.entities:
            if entity.team is shooter.team:
                continue
            if math.dist(shooter.pos, entity.pos) <= self.soundReport:
                entity.report(
                    matchInfo, f"I hear fire from a {self.name}.",
                    teamReport=False, critical=False,
                )

    def shootAt(self, matchInfo, pos, aimedLimb=None):
        """Spend resources and resolve every projectile fired at a map position."""

        if self.isLauncher:
            return self.launchAt(matchInfo, pos)

        #check if enough resources
        if self.charges is not None and self.charges - 1 < 0:
            print("Out of ammo!")
            return
        if self.maxRange is not None and math.dist(matchInfo.pov.pos, pos) > self.maxRange:
            print(f"Target is beyond this weapon's {self.maxRange}-tile range.")
            return
        aimApCost = 1 if aimedLimb is not None else 0
        if matchInfo.pov.ap - (self.apCost + aimApCost) < 0:
            print("Out of action points!")
            return
        if matchInfo.pov.energy - self.energyCost < 0:
            print("Not enough energy to fire!")
            return

        if self.charges is not None:
            self.charges -= 1
        matchInfo.pov.ap -= self.apCost + aimApCost
        matchInfo.pov.energy -= self.energyCost
        # Store the attempted location even on a miss so a follow-up shot can
        # be ordered without re-entering coordinates.
        matchInfo.pov.lastFiredAt = list(pos)

        #enemies will report noise
        self.emitSound(matchInfo)

        accuracyRequired = self.accuracy_required(matchInfo, matchInfo.pov, pos)

        target = next((entity for entity in matchInfo.entities if entity.pos == pos), None)

        i = 1
        while i <= self.projectileCount:
            i += 1
            movementMultiplier = 1
            if matchInfo.pov.speed > 0:
                movementMultiplier = 1 - ((random.randint(0, self.speedPenalty) * matchInfo.pov.speed) / 100)
            effectiveAccuracy = self.accuracy * self.accuracyMultiplier * movementMultiplier
            hitChance = self._hit_chance(matchInfo.pov, target, effectiveAccuracy, accuracyRequired)

            if random.randint(1, 100) > hitChance:
                print("Shot missed!")
            else:
                print("Shot hit!")
                if target is not None:
                    targetLimb = aimedLimb if aimedLimb in target.mechClass.limbList else random.choice(target.mechClass.limbList)
                    targetLimb.damage(matchInfo, self.dmg, self.name, armorPiercing = self.piercing, armorDamage = self.armorDamage)

        matchInfo.advTurn = True

    def launchAt(self, matchInfo, targetPosition):
        """Fire a delayed shell that scatters and resolves on a future turn."""
        ammo = self.selected_ammo
        if ammo.charges is not None and ammo.charges < 1:
            print("Out of ammo!")
            return
        distance = math.dist(matchInfo.pov.pos, targetPosition)
        profile = self.launcher_profile(distance)
        if profile is None:
            farRange = ammo.rangeBands["far"][0]
            print(f"Target is beyond this launcher's {farRange}-tile far range.")
            return
        if matchInfo.pov.ap < self.apCost:
            print("Out of action points!")
            return
        if matchInfo.pov.energy < self.energyCost:
            print("Not enough energy to fire!")
            return

        if ammo.charges is not None:
            ammo.charges -= 1
        matchInfo.pov.ap -= self.apCost
        matchInfo.pov.energy -= self.energyCost
        matchInfo.pov.lastFiredAt = list(targetPosition)
        self.emitSound(matchInfo)

        impactPosition = artillery.scatter_position(
            matchInfo, targetPosition, profile["inaccuracy"],
        )
        impact = artillery.schedule_impact(
            matchInfo,
            impactPosition,
            # The firing squad's turn is still in progress.  Add one pending
            # handoff so a one-turn shell lands only after one *complete*
            # future squad turn, rather than as soon as the player ends now.
            profile["turns"] + 1,
            ammo.blastRadius,
            ammo.blastSize,
            max(0, self.dmg + ammo.damageModifier - profile["damage_falloff"]),
            f"{self.name} {ammo.name}",
            ammo.payload,
            ammo.effectRadius,
            ammo.effectTurns,
            ammo.scoutVision,
            matchInfo.pov.team,
            ammo.igniteChance,
            self.soundReport,
        )
        if profile["turns"] == 0:
            print(f"{self.name} fired on its {profile['name']} profile. Impact is immediate.")
            # A zero-turn profile resolves this shell alone.  Calling the
            # normal advancement routine here would incorrectly age every
            # other projectile already in the air.
            matchInfo.pendingImpacts.remove(impact)
            artillery.resolve_impact(matchInfo, impact)
        else:
            print(
                f"{self.name} fired on its {profile['name']} profile. "
                f"Impact expected after {profile['turns']} completed turn(s)."
            )
        matchInfo.advTurn = True

    def launcher_profile(self, distance):
        """Return the first range band able to reach ``distance``, if any."""
        if not self.isLauncher:
            return None
        return self.selected_ammo.profile(distance)

    @property
    def selected_ammo(self):
        """Return the ammunition currently loaded in this launcher."""
        return self.ammoTypes[self.selectedAmmoIndex]

    def select_ammo(self, index):
        """Load one available ammunition type by its zero-based menu index."""
        if not 0 <= index < len(self.ammoTypes):
            raise ValueError("Ammo index is not available on this launcher.")
        self.selectedAmmoIndex = index

    def _hit_chance(self, shooter, target, effectiveAccuracy, accuracyRequired):
        """Return the per-projectile hit chance after terrain and size effects."""
        if effectiveAccuracy < accuracyRequired:
            return 0

        # Meeting the terrain requirement creates the first 10% chance. Every
        # further point adds 5%, then target size modifies the final result.
        baseChance = 10 + ((effectiveAccuracy - accuracyRequired) * 5)
        targetSize = target.size if target is not None else shooter.size
        sizeMultiplier = 1.2 ** (targetSize - shooter.size)
        return min(99, max(10, round(baseChance * sizeMultiplier)))

    def accuracy_required(self, matchInfo, shooter, position):
        """Return the terrain accuracy cost of a shot path.

        The firing menu uses this same helper as the actual attack, so its
        chance preview cannot drift away from the resolved combat rules.
        """
        path = matchInfo.ListInterceptingSquares(shooter.pos, position)
        startingCell = matchInfo.map[shooter.pos[1]][shooter.pos[0]]
        ignored_cells = [*startingCell.nList, startingCell]
        path = [cell for cell in path if cell not in ignored_cells]
        return sum(cell.visualAbsorption for cell in path)

    def hit_chance_range(self, matchInfo, shooter, target, position):
        """Return the displayed low/high hit chance for a resolved target.

        Actual attacks roll a movement penalty for every projectile.  A still
        shooter therefore gets one exact value, while a moving shooter gets a
        truthful range covering its possible individual projectile chances.
        """
        accuracy_required = self.accuracy_required(matchInfo, shooter, position)
        maximum_accuracy = self.accuracy * self.accuracyMultiplier
        minimum_multiplier = max(0, 1 - ((self.speedPenalty * shooter.speed) / 100))
        minimum_accuracy = maximum_accuracy * minimum_multiplier
        chances = (
            self._hit_chance(shooter, target, minimum_accuracy, accuracy_required),
            self._hit_chance(shooter, target, maximum_accuracy, accuracy_required),
        )
        return min(chances), max(chances)

    def printShortDesc(self):

        charges = "Unlimited" if self.charges is None else f"{self.charges}/{self.maxCharges}"
        weaponType = "Launcher" if self.isLauncher else "Weapon"
        return f"[{weaponType}: {self.name} | Charges:({charges}) AP Cost:{self.apCost} Energy Cost:{self.energyCost}]"


#clean up module system and make it work (not updating)
class Module: #supposed to be superclass but couldn't figure it out
    """Damageable modifier attached to a mech part."""
    def __init__(self, name, attrNames, bonusType, statChangeList, desc = ""): #[destroyed bonus, damaged bonus, good bonus]

        self.name = name
        self.statNames = attrNames
        self.modType = bonusType #0 makes no stat changes
        self.status = 2 #[destroyed, damaged, good]
        self.statsArray = statChangeList
        self.desc = desc

    def restore(self):
        self.status = 2

    def damage(self, matchInfo=None):
        if self.status > 0:
            self.status -= 1
        else:
            pass

    def repair(self):
        if self.status < 2:
            self.status += 1
        else:
            pass

class Cockpit(Module):
    """Module that records the pilot and crew required to operate a mech."""
    def __init__ (self, name, attrNames, bonusType, statChangeList, pilot, crewServed, desc = ""):
        super().__init__(name, attrNames, bonusType, statChangeList, desc = "")
        self.pilot = pilot
        self.crewServed = crewServed
        self.mech = None

        #TODO add pilot skills and levels then make them apply

    def damage(self, matchInfo=None):
        """Warn on pilot injury and destroy the mech when the cockpit fails."""
        previous_status = self.status
        super().damage(matchInfo)

        if matchInfo is None or self.mech is None or previous_status == self.status:
            return

        if self.status == 1:
            self.mech.report(
                matchInfo,
                "Cockpit hit! Pilot injured; cockpit integrity is failing.",
                critical=True,
            )
        elif self.status == 0:
            self.mech.report(
                matchInfo,
                "Cockpit destroyed! Mech is no longer operational.",
                critical=True,
            )
            self.mech.destroy(matchInfo)
