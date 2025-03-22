import gameClasses as C
import copy

#MechModules do not touch Init stats

    #setModules
radarDetector = C.Module("Lancer Radar Detector", ["passiveRadar"], 1, [[False, False, True]], desc="")
chainGunAuto = C.Module("ChainGun Bolt", ["bonusProjectileCount"], 1, [[1, 2, 3]], desc="")
lightWeightFrame = C.Module("light Lancer Frame", ["bonusMP"], 1, [[-2 , -1, 2]], desc= "A lightweight frame to increase mobility, at the cost of structural integrity")
exosuitLegMotor = C.Module("Exosuit Leg Motors", ["multiMP"], 1,  [[.5 , .8 , 1]], desc= "Motors that run the Exosuit's legs. Made resilient for the fact that mobility is essential for Lancers Class Mechs")
chainGunHoloSight = C.Module("ChainGun Holosight", ["accuracyPenalty"], 1, [[.75, .9, 1]], desc="")

    #nonModules-Modules
critProtection = C.Module("Anti-spalling Foam", ["Na"], 0, [["Na", "Na", "Na"]], desc="")

    #MechLimbs
greatHelm= C.Helm( "Great Helm", 5, 30, [critProtection], 6, 12, 0, desc = "A Lancer Power Armor Helm with a suite of sensor data displays inside")
lancerPowerArmor= C.Hull( "Lancer Power Armor", 5, 25, [], 20, 1, 250, 2, desc = "The namesake of the Lancer Class mechs. Not a true mech, but a very large set of power Armor. Extremely fast and agile compared to mechs of other classes, but lack data sensors, radar, and means of serious ranged damage.")
lancerPowerArmorLegs= C.Legs( "Lancer Power Armor Legs", 5, 25, [exosuitLegMotor, lightWeightFrame], 4, desc = "Exosuit powered legs covered in armor")
godHelm= C.Helm( "God Helm", 5, 30,[radarDetector, critProtection], 100, 15, 600, desc = "Dev Tool")
godHull= C.Hull( "God Hull", 5, 30, [critProtection, critProtection], 150, 40, 250, 2, desc = "Dev Tool")
kikiLegs= C.Legs( "God Legs", 5, 30, [exosuitLegMotor, lightWeightFrame], 100, desc = "Dev Tool")
lancerChainGun= C.WeaponLimb( "ChainGun", 8, 30, [chainGunAuto, chainGunHoloSight], 8, 20, 20, 60, projectileCount = 3, desc = "")

    #MechClasses
lancer = C.MechClass("Lancer Type.A" , "p", "dark_grey", lancerPowerArmor, greatHelm, lancerPowerArmorLegs, [lancerChainGun], "")
test = C.MechClass("Test" , "@", "yellow", godHull, godHelm, kikiLegs,[copy.deepcopy(lancerChainGun), copy.deepcopy(lancerChainGun)],"")
