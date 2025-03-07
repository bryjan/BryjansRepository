import gameClasses as C
import copy

#MechModules do not touch Init stats

    #setModules
radarDetector = C.Module("Lancer Radar Detector", "passiveRadar", 3, [False, False, True], desc="")
chainGunAuto = C.Module("ChainGun Bolt", "projectileCount", 3, [1, 2, 3], desc="")

    #flatModules
lightWeightFrame = C.Module("light Lancer Frame", "mp", 2, [-2 , -1, 2], desc= "A lightweight frame to increase mobility, at the cost of structural integrity")

    #coreModules
exosuitLegMotor = C.Module("Exosuit Leg Motors", "mp", 1,  [.5 , .8 , 1], desc= "Motors that run the Exosuit's legs. Made resilient for the fact that mobility is essential for Lancers Class Mechs")
chainGunHoloSIght = C.Module("ChainGun Holosight", "accuracyPenalty", 1, [.75, .9, 1], desc="")

#MechLimbs
greatHelm= C.Helm( "Great Helm", 5, 30, [], 6, 12, 50, desc = "A Lancer Power Armor Helm with a suite of sensor data displays inside")
lancerPowerArmor= C.Hull( "Lancer Power Armor", 5, 25, [lightWeightFrame], 20, 1, 250, 2, desc = "The namesake of the Lancer Class mechs. Not a true mech, but a very large set of power Armor. Extremely fast and agile compared to mechs of other classes, but lack data sensors, radar, and means of serious ranged damage.")
lancerPowerArmorLegs= C.Legs( "Lancer Power Armor Legs", 5, 25, [exosuitLegMotor], 4, desc = "Exosuit powered legs covered in armor")
godHelm= C.Helm( "God Helm", 5, 30,[radarDetector], 100, 15, 600, desc = "Dev Tool")
godHull= C.Hull( "God Hull", 5, 30, [], 150, 40, 250, 2, desc = "Dev Tool")
kikiLegs= C.Legs( "God Legs", 5, 30, [exosuitLegMotor, lightWeightFrame], 100, desc = "Dev Tool")
lancerChainGun= C.WeaponLimb( "ChainGun", 8, 30, [chainGunAuto, chainGunHoloSIght], 8, 40, 20, 60, projectileCount = 3, desc = "")

#MechClasses
lancer = C.MechClass("Lancer Type.A" , "p", "dark_grey", lancerPowerArmor, greatHelm, lancerPowerArmorLegs, [lancerChainGun], "")
test = C.MechClass("Test" , "@", "yellow", godHull, godHelm, kikiLegs,[copy.deepcopy(lancerChainGun), copy.deepcopy(lancerChainGun)],"")
