import gameClasses as C

#MechModules do not touch Init stats

    #setModules
radarDetector = C.Module("Lancer Radar Detector", "passiveRadar", 3, [False, False, True], desc="")

    #flatModules
lightWeightFrame = C.Module("light Lancer Frame", "mp", 2, [-2 , -1, 2], desc= "A lightweight frame to increase mobility, at the cost of structural integrity")

    #coreModules
exosuitLegMotor = C.Module("Exosuit Leg Motors", "mp", 1,  [.5 , .8 , 1], desc= "Motors that run the Exosuit's legs. Made resilient for the fact that mobility is essential for Lancers Class Mechs")

#MechLimbs
greatHelm= C.Helm( "Great Helm", 5, 25, [], 6, 12, 50, desc = "A Lancer Power Armor Helm with a suite of sensor data displays inside")
lancerPowerArmor= C.Hull( "Lancer Power Armor", 5, 25, [lightWeightFrame], 20, 1, 250, 2, desc = "The namesake of the Lancer Class mechs. Not a true mech, but a very large set of power Armor. Extremely fast and agile compared to mechs of other classes, but lack data sensors, radar, and means of serious ranged damage.")
lancerPowerArmorLegs= C.Legs( "Lancer Power Armor Legs", 5, 25, [exosuitLegMotor], 4, desc = "Exosuit powered legs covered in armor")
godHelm= C.Helm( "God Helm", 5, 25,[radarDetector], 10, 15, 600, desc = "Dev Tool")
godHull= C.Hull( "God Hull", 5, 25, [], 50, 10, 250, 2, desc = "Dev Tool")
kikiLegs= C.Legs( "God Legs", 5, 25, [exosuitLegMotor, lightWeightFrame], 10, desc = "Dev Tool")
#MechClasses
lancer = C.MechClass("Lancer Type.A" , "p", "dark_grey", lancerPowerArmor, greatHelm, lancerPowerArmorLegs, [], "")
test = C.MechClass("Test" , "@", "yellow", godHull, godHelm, kikiLegs,[],"")
