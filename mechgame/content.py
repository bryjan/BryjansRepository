"""Reusable mech and pilot definitions plus example scenarios."""

from .entities import Entity, Pilot
from .mechs import Helm, Hull, Legs, MechClass, Module, WeaponLimb
from .teams import Squad, Team


def create_lancer_class():
    """Return a fresh Lancer definition so matches never share mutable parts."""
    radar_detector = Module(name="Lancer Radar Detector", attrNames=["passiveRadar"], bonusType=1, statChangeList=[[False, False, True]])
    chain_gun_auto = Module(name="ChainGun Bolt", attrNames=["bonusProjectileCount"], bonusType=1, statChangeList=[[-1, 0, 2]])
    light_frame = Module(name="light Lancer Frame", attrNames=["bonusMP"], bonusType=1, statChangeList=[[-2, -1, 2]])
    leg_motor = Module(name="Exosuit Leg Motors", attrNames=["multiMP"], bonusType=1, statChangeList=[[.5, .8, 1]])
    holo_sight = Module(name="ChainGun Holosight", attrNames=["accuracyPenalty"], bonusType=1, statChangeList=[[.75, .9, 1]])
    crit_protection = Module(name="Anti-spalling Foam", attrNames=["Na"], bonusType=0, statChangeList=[["Na", "Na", "Na"]])

    helm = Helm(name="Great Helm", armor=5, hp=30, moduleList=[crit_protection], ap=6, visualPower=12, radarPower=0, radarEnergyCost=0)
    # Lancers are slightly harder than a typical size-2 unit to find.
    hull = Hull(name="Lancer Power Armor", armor=5, hp=25, moduleList=[], pwrCapacity=20, pwrGen=1, radarSig=100, size=2)
    legs = Legs(name="Lancer Power Armor Legs", armor=5, hp=25, moduleList=[leg_motor, light_frame], speed=4)
    gun = WeaponLimb(name="ChainGun", armor=8, hp=30, moduleList=[chain_gun_auto, holo_sight], damage=8, accuracy=20, soundRep=20, charges=60, projectileCount=3)
    return MechClass(name="Lancer Type.A", symbol="p", color="dark_grey", mechHull=hull, mechHelm=helm, mechLeg=legs, limblist=[gun])


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
