"""Reusable mech and pilot definitions plus example scenarios."""

from .models import Entity, Helm, Hull, Legs, MechClass, Module, Pilot, Squad, Team, WeaponLimb


def create_lancer_class():
    """Return a fresh Lancer definition so matches never share mutable parts."""
    radar_detector = Module("Lancer Radar Detector", ["passiveRadar"], 1, [[False, False, True]])
    chain_gun_auto = Module("ChainGun Bolt", ["bonusProjectileCount"], 1, [[-1, 0, 2]])
    light_frame = Module("light Lancer Frame", ["bonusMP"], 1, [[-2, -1, 2]])
    leg_motor = Module("Exosuit Leg Motors", ["multiMP"], 1, [[.5, .8, 1]])
    holo_sight = Module("ChainGun Holosight", ["accuracyPenalty"], 1, [[.75, .9, 1]])
    crit_protection = Module("Anti-spalling Foam", ["Na"], 0, [["Na", "Na", "Na"]])

    helm = Helm("Great Helm", 5, 30, [crit_protection], 6, 12, 0)
    hull = Hull("Lancer Power Armor", 5, 25, [], 20, 1, 250, 2)
    legs = Legs("Lancer Power Armor Legs", 5, 25, [leg_motor, light_frame], 4)
    gun = WeaponLimb("ChainGun", 8, 30, [chain_gun_auto, holo_sight], 8, 20, 20, 60, projectileCount=3)
    return MechClass("Lancer Type.A", "p", "dark_grey", hull, helm, legs, [gun])


def _create_demo_mechs(*pilot_names):
    """Create independent Lancers for the named pilots in a demo squad."""
    return [Entity(create_lancer_class(), Pilot(name)) for name in pilot_names]


def create_demo_teams():
    """Create the small playable scenario previously embedded in main.py."""
    player_mechs = _create_demo_mechs("Kiki", "Bryan")
    enemy_mechs = _create_demo_mechs("Wraith", "Ghost")
    player = Team("Player Team", [Squad("Player Squad", player_mechs, "Combat", playerControlled=True)])
    enemies = Team("Enemy Team", [Squad("Enemy Squad", enemy_mechs, "Combat")])
    return [enemies, player]
