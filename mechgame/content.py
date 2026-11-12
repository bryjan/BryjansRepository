"""Reusable mech and pilot definitions plus example scenarios."""

from .entities import Entity, Pilot
from .mechs import Helm, Hull, Legs, MechClass, Module, WeaponLimb
from .teams import Squad, Team


def _create_lancer_modules():
    """Return fresh modules shared by all Lancer variants.

    Parts and modules can be damaged during a match, so each factory call must
    create its own modules instead of sharing mutable instances between mechs.
    """
    return {
        "passive_radar": Module(name="Passive Radar Detector", attrNames=["passiveRadar"], bonusType=1, statChangeList=[[False, False, True]]),
        "light_frame": Module(name="Lancer Light Frame", attrNames=["bonusMP"], bonusType=1, statChangeList=[[-2, -1, 2]]),
        "leg_motors": Module(name="Exosuit Leg Motors", attrNames=["multiMP"], bonusType=1, statChangeList=[[.5, .8, 1]]),
        # An intact sight improves terrain-limited accuracy. Damage removes
        # that benefit before a destroyed sight imposes a real penalty.
        "holosight": Module(name="Holosight", attrNames=["accuracyPenalty"], bonusType=1, statChangeList=[[.75, 1, 1.2]]),
        "anti_spalling": Module(name="Anti-Spalling Foam", attrNames=["Na"], bonusType=0, statChangeList=[["Na", "Na", "Na"]]),
    }


def create_lancer_class():
    """Return a fresh Lancer definition so matches never share mutable parts."""
    modules = _create_lancer_modules()
    chain_gun_auto = Module(name="ChainGun Bolt", attrNames=["bonusProjectileCount"], bonusType=1, statChangeList=[[-1, 0, 2]])

    helm = Helm(name="Great Helm", armor=5, hp=30, moduleList=[modules["anti_spalling"], modules["passive_radar"]], ap=6, visualPower=14, radarPower=0, radarEnergyCost=0)
    # Lancers are slightly harder than a typical size-2 unit to find.
    hull = Hull(name="Lancer Power Armor", armor=5, hp=25, moduleList=[], pwrCapacity=20, pwrGen=3, radarSig=100, size=2)
    legs = Legs(name="Lancer Power Armor Legs", armor=5, hp=25, moduleList=[modules["leg_motors"], modules["light_frame"]], speed=4)
    gun = WeaponLimb(name="ChainGun", armor=8, hp=30, moduleList=[chain_gun_auto, modules["holosight"]], damage=9, accuracy=20, soundRep=20, charges=60, projectileCount=3)
    return MechClass(name="Lancer Type.A", symbol="p", color="dark_grey", mechHull=hull, mechHelm=helm, mechLeg=legs, limblist=[gun])


def create_sensor_lancer_class():
    """Return a fast Lancer variant built for short-range active scouting."""
    modules = _create_lancer_modules()
    active_radar = Module(
        name="Standard Active Radar Array",
        attrNames=["bonusRadarPower", "bonusRadarEnergyCost"],
        bonusType=1,
        statChangeList=[[0, 150, 200], [0, 3, 3]],
    )

    helm = Helm(name="Pathfinder Sensor Helm", armor=4, hp=25, moduleList=[modules["anti_spalling"], modules["passive_radar"], active_radar], ap=6, visualPower=14, radarPower=0, radarEnergyCost=0)
    hull = Hull(name="Pathfinder Lancer Hull", armor=4, hp=22, moduleList=[], pwrCapacity=20, pwrGen=3, radarSig=100, size=2)
    legs = Legs(name="Pathfinder Lancer Legs", armor=4, hp=22, moduleList=[modules["leg_motors"], modules["light_frame"]], speed=4)
    rifle = WeaponLimb(name="Scout Rifle", armor=6, hp=24, moduleList=[modules["holosight"]], damage=10, accuracy=30, soundRep=20, charges=60)
    return MechClass(name="Lancer Type.S Pathfinder", symbol="s", color="cyan", mechHull=hull, mechHelm=helm, mechLeg=legs, limblist=[rifle])


def _create_demo_mechs(*pilot_names):
    """Create independent Lancers for the named pilots in a demo squad."""
    return [Entity(create_lancer_class(), Pilot(name)) for name in pilot_names]


def create_demo_teams():
    """Create the small playable scenario previously embedded in main.py."""
    player_mechs = [
        Entity(create_sensor_lancer_class(), Pilot("Kiki")),
        Entity(create_lancer_class(), Pilot("Bryan")),
    ]
    enemy_mechs = _create_demo_mechs("Wraith", "Ghost")
    player = Team("Player Team", [Squad("Player Squad", player_mechs, "Combat", playerControlled=True)])
    enemies = Team("Enemy Team", [Squad("Enemy Squad", enemy_mechs, "Combat")])
    return [enemies, player]
