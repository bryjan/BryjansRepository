"""Named factories for all reusable mech content.

Factories return new objects every time. Match objects are mutable because
they can take damage, so the catalog never shares an instance between callers.
"""

from .mechs import Helm, Hull, Legs, MechClass, Module, WeaponLimb


SIZE_CLASS_NAMES = {
    0: "flat", 1: "tiny", 2: "small", 3: "medium", 4: "large",
    5: "huge", 6: "titanic",
}


def _module_passive_radar_detector():
    return Module("Passive Radar Detector", ["passiveRadar"], 1, [[False, False, True]])


def _module_lancer_light_frame():
    return Module("Lancer Light Frame", ["bonusMP"], 1, [[-2, -1, 2]])


def _module_exosuit_leg_motors():
    return Module("Exosuit Leg Motors", ["multiMP"], 1, [[.5, .8, 1]])


def _module_holosight():
    return Module("Holosight", ["accuracyPenalty"], 1, [[.75, 1, 1.2]])


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


MODULE_FACTORIES = {
    "anti_spalling_foam": _module_anti_spalling_foam,
    "chaingun_bolt": _module_chaingun_bolt,
    "exosuit_leg_motors": _module_exosuit_leg_motors,
    "holosight": _module_holosight,
    "lancer_light_frame": _module_lancer_light_frame,
    "passive_radar_detector": _module_passive_radar_detector,
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


MECH_FACTORIES = {
    2: {"lancer.type_a": _lancer_type_a, "lancer.pathfinder": _lancer_pathfinder},
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
            "modules": tuple(MODULE_FACTORIES) if class_size == 2 else (),
        }
        for class_size, class_name in sizes.items()
    }
