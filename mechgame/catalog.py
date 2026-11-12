"""Named factories for all reusable mech content.

Factories return new objects every time. Match objects are mutable because
they can take damage, so the catalog never shares an instance between callers.
"""

from .mechs import Helm, Hull, Legs, MechClass, Module, WeaponLimb


SIZE_CLASS_NAMES = {
    0: "flat", 1: "tiny", 2: "small", 3: "medium", 4: "large",
    5: "huge", 6: "titanic",
}

# Module stat arrays always use this order: destroyed, damaged, intact.
# Keeping that convention beside the factories makes balance values readable.

def _module_passive_radar_detector():
    return Module("Passive Radar Detector", ["passiveRadar"], 1, [[False, False, True]])


def _module_lancer_light_frame():
    return Module("Lancer Light Frame", ["bonusMP"], 1, [[-2, -1, 2]])


def _module_exosuit_leg_motors():
    return Module("Exosuit Leg Motors", ["multiMP"], 1, [[.5, .8, 1]])


def _module_holosight():
    return Module("Holosight", ["accuracyMultiplier"], 1, [[.75, 1, 1.2]])


def _module_anti_spalling_foam():
    return Module("Anti-Spalling Foam", ["Na"], 0, [["Na", "Na", "Na"]])


def _module_chaingun_bolt():
    return Module("ChainGun Bolt", ["bonusProjectileCount"], 1, [[-1, 0, 2]])


def _module_standard_active_radar_array():
    return Module(
        "Standard Active Radar Array",
        ["bonusRadarPower", "bonusRadarEnergyCost"],
        1,
        [[0, 150, 200], [0, 3, 3]],
    )


def _module_kestrel_active_radar_array():
    return Module(
        "Kestrel Active Radar Array",
        ["bonusRadarPower", "bonusRadarEnergyCost"],
        1,
        [[0, 175, 250], [0, 2, 2]],
    )


def _module_kestrel_leg_actuators():
    """Make leg damage Kestrel's primary mobility weakness.

    Intact actuators preserve the Kestrel's 5 MP. Damage reduces it to 4 MP,
    while a destroyed actuator pack leaves only 2 MP for emergency movement.
    """
    return Module("Kestrel Leg Actuators", ["bonusMP"], 1, [[-3, -1, 0]])


def _module_kestrel_reserve_capacitor():
    """Supply the Kestrel's burst reserve and its final fourth energy regen."""
    return Module(
        "Kestrel Reserve Capacitor",
        ["bonusEnergy", "bonusEnergyGen"],
        1,
        [[0, 5, 10], [0, 0, 1]],
    )


def _module_efficient_combat_reactor():
    """Give Bastion sustained output without relying on a huge reserve."""
    return Module(
        "Efficient Combat Reactor",
        ["bonusEnergy", "bonusEnergyGen"],
        1,
        [[0, 3, 6], [0, 0, 1]],
    )


def _module_reinforced_leg_drives():
    """Keep Bastion at full speed until its durable drives are destroyed."""
    return Module("Reinforced Leg Drives", ["bonusMP"], 1, [[-1, 0, 0]])


MODULE_FACTORIES = {
    "anti_spalling_foam": _module_anti_spalling_foam,
    "chaingun_bolt": _module_chaingun_bolt,
    "exosuit_leg_motors": _module_exosuit_leg_motors,
    "efficient_combat_reactor": _module_efficient_combat_reactor,
    "holosight": _module_holosight,
    "kestrel_active_radar_array": _module_kestrel_active_radar_array,
    "kestrel_leg_actuators": _module_kestrel_leg_actuators,
    "kestrel_reserve_capacitor": _module_kestrel_reserve_capacitor,
    "lancer_light_frame": _module_lancer_light_frame,
    "passive_radar_detector": _module_passive_radar_detector,
    "reinforced_leg_drives": _module_reinforced_leg_drives,
    "standard_active_radar_array": _module_standard_active_radar_array,
}


def create_module(module_id):
    """Build a fresh module from its stable catalog ID."""
    try:
        return MODULE_FACTORIES[module_id]()
    except KeyError as error:
        raise ValueError(f"Unknown module '{module_id}'.") from error


def _standard_lancer_helm():
    return Helm(
        "Great Helm", 5, 30,
        [create_module("anti_spalling_foam"), create_module("passive_radar_detector")],
        ap=6, visualPower=14, radarPower=0, radarEnergyCost=0,
    )


def _pathfinder_sensor_helm():
    return Helm(
        "Pathfinder Sensor Helm", 4, 25,
        [
            create_module("anti_spalling_foam"),
            create_module("passive_radar_detector"),
            create_module("standard_active_radar_array"),
        ],
        ap=6, visualPower=14, radarPower=0, radarEnergyCost=0,
    )


def _standard_lancer_hull():
    return Hull("Lancer Power Armor", 5, 25, [], pwrCapacity=20, pwrGen=3, radarSig=100, size=2)


def _pathfinder_lancer_hull():
    return Hull("Pathfinder Lancer Hull", 4, 22, [], pwrCapacity=20, pwrGen=3, radarSig=100, size=2)


def _standard_lancer_legs():
    return Legs(
        "Lancer Power Armor Legs", 5, 25,
        [create_module("exosuit_leg_motors"), create_module("lancer_light_frame")],
        speed=4,
    )


def _pathfinder_lancer_legs():
    return Legs(
        "Pathfinder Lancer Legs", 4, 22,
        [create_module("exosuit_leg_motors"), create_module("lancer_light_frame")],
        speed=4,
    )


def _chaingun():
    return WeaponLimb(
        "ChainGun", 8, 30,
        [create_module("chaingun_bolt"), create_module("holosight")],
        damage=9, accuracy=20, soundRep=20, charges=60, projectileCount=3,
    )


def _scout_rifle():
    return WeaponLimb("Scout Rifle", 6, 24, [create_module("holosight")], damage=10, accuracy=30, soundRep=20, charges=60)


def _kestrel_sensor_helm():
    return Helm(
        "Kestrel Sensor Helm", 9, 45,
        [
            create_module("anti_spalling_foam"),
            create_module("passive_radar_detector"),
            create_module("kestrel_active_radar_array"),
        ],
        ap=8, visualPower=16, radarPower=0, radarEnergyCost=0,
    )


def _kestrel_hull():
    # The capacitor brings this 40/3 chassis to its intended 50 reserve and
    # 4 regeneration. Losing it removes that performance advantage.
    return Hull(
        "Kestrel Hull", 10, 50,
        [
            create_module("anti_spalling_foam"),
            create_module("kestrel_reserve_capacitor"),
        ],
        pwrCapacity=40, pwrGen=3, radarSig=250, size=3,
    )


def _kestrel_legs():
    return Legs(
        "Kestrel Legs", 7, 40,
        [create_module("kestrel_leg_actuators")],
        speed=5,
    )


def _kestrel_energy_beam():
    return WeaponLimb(
        "Kestrel Energy Beam", 8, 30, [], damage=12, accuracy=34,
        soundRep=20, charges=None, apCost=2, energyCost=4, maxRange=32,
    )


def _bastion_helm():
    return Helm(
        "Bastion Helm", 11, 55,
        [create_module("anti_spalling_foam"), create_module("anti_spalling_foam")],
        ap=7, visualPower=15, radarPower=0, radarEnergyCost=0,
    )


def _bastion_hull():
    return Hull(
        "Bastion Hull", 12, 65,
        [
            create_module("anti_spalling_foam"),
            create_module("anti_spalling_foam"),
            create_module("efficient_combat_reactor"),
        ],
        pwrCapacity=26, pwrGen=5, radarSig=320, size=3,
    )


def _bastion_legs():
    return Legs("Bastion Legs", 9, 55, [create_module("reinforced_leg_drives")], speed=4)


def _heavy_melting_beam():
    return WeaponLimb(
        "Heavy Melting Beam", 10, 45, [], damage=20, accuracy=30,
        soundRep=20, charges=None, apCost=2, energyCost=2,
        armorDamage=2, maxRange=28,
    )


def _sustained_chaingun():
    return WeaponLimb(
        "Sustained ChainGun", 8, 30,
        [create_module("chaingun_bolt"), create_module("holosight")],
        damage=9, accuracy=20, soundRep=20, charges=120, projectileCount=3,
    )


PART_FACTORIES = {
    2: {
        "lancer.standard_helm": _standard_lancer_helm,
        "pathfinder.sensor_helm": _pathfinder_sensor_helm,
        "lancer.standard_hull": _standard_lancer_hull,
        "pathfinder.hull": _pathfinder_lancer_hull,
        "lancer.standard_legs": _standard_lancer_legs,
        "pathfinder.legs": _pathfinder_lancer_legs,
        "chaingun": _chaingun,
        "scout_rifle": _scout_rifle,
    },
    3: {
        "bastion.helm": _bastion_helm,
        "bastion.hull": _bastion_hull,
        "bastion.legs": _bastion_legs,
        "heavy_melting_beam": _heavy_melting_beam,
        "kestrel.sensor_helm": _kestrel_sensor_helm,
        "kestrel.hull": _kestrel_hull,
        "kestrel.legs": _kestrel_legs,
        "kestrel_energy_beam": _kestrel_energy_beam,
        "sustained_chaingun": _sustained_chaingun,
    },
}


def create_part(size, part_id):
    """Build a fresh part from a size class and a stable catalog ID."""
    try:
        return PART_FACTORIES[size][part_id]()
    except KeyError as error:
        raise ValueError(f"Unknown size-{size} part '{part_id}'.") from error


def _lancer_type_a():
    return MechClass(
        "Lancer Type.A", "p", "dark_grey",
        create_part(2, "lancer.standard_hull"),
        create_part(2, "lancer.standard_helm"),
        create_part(2, "lancer.standard_legs"),
        [create_part(2, "chaingun")],
    )


def _lancer_pathfinder():
    return MechClass(
        "Lancer Type.S Pathfinder", "s", "cyan",
        create_part(2, "pathfinder.hull"),
        create_part(2, "pathfinder.sensor_helm"),
        create_part(2, "pathfinder.legs"),
        [create_part(2, "scout_rifle")],
    )


def _kestrel():
    return MechClass(
        "Kestrel", "K", "light_blue",
        create_part(3, "kestrel.hull"),
        create_part(3, "kestrel.sensor_helm"),
        create_part(3, "kestrel.legs"),
        [create_part(3, "kestrel_energy_beam")],
    )


def _bastion():
    return MechClass(
        "Bastion", "B", "green",
        create_part(3, "bastion.hull"),
        create_part(3, "bastion.helm"),
        create_part(3, "bastion.legs"),
        [create_part(3, "heavy_melting_beam"), create_part(3, "sustained_chaingun")],
    )


MECH_FACTORIES = {
    2: {"lancer.type_a": _lancer_type_a, "lancer.pathfinder": _lancer_pathfinder},
    3: {"bastion": _bastion, "kestrel": _kestrel},
}


def create_mech(mech_id):
    """Build a fresh mech by its stable catalog ID."""
    for mechs in MECH_FACTORIES.values():
        if mech_id in mechs:
            return mechs[mech_id]()
    raise ValueError(f"Unknown mech '{mech_id}'.")


def list_catalog(size=None):
    """Return available IDs grouped by class size."""
    sizes = SIZE_CLASS_NAMES if size is None else {size: SIZE_CLASS_NAMES[size]}
    return {
        class_size: {
            "name": class_name,
            "mechs": tuple(MECH_FACTORIES.get(class_size, {})),
            "parts": tuple(PART_FACTORIES.get(class_size, {})),
            "modules": tuple(MODULE_FACTORIES) if class_size in PART_FACTORIES else (),
        }
        for class_size, class_name in sizes.items()
    }
