"""Persistent Mercenary Mode state, independent of one-off skirmishes.

The campaign deliberately stores durable strategic information only: money,
research, pilot availability, hangar limits, chosen deployments, and mission
offers. Tactical match construction and post-mission salvage are future work;
keeping them outside this module prevents a contract from mutating skirmish
state before a battle actually begins.
"""

from dataclasses import dataclass
import random

from .catalog import create_mech
from .entities import Pilot
from .names import generate_pilot_name

__all__ = ["CampaignMission", "Deployment", "MercenaryCampaign"]


@dataclass(frozen=True)
class CampaignMission:
    """A contract offered to the company before a tactical map is created."""

    mission_id: int
    kind: str
    title: str
    payout: int
    description: str
    required_roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class Deployment:
    """One pilot and researched chassis committed to a campaign slot."""

    pilot_name: str
    mech_id: str
    size: int


MISSION_TEMPLATES = (
    ("pilot_recovery", "Pilot Recovery", 650,
     "Locate and extract a missing pilot before hostile forces close in.", ("scout", "sensor")),
    ("attack_military_base", "Raid Military Base", 1_100,
     "Strike an enemy military base and disrupt its defenders.", ("front_line", "fire_support")),
    ("patrol_map", "Frontier Patrol", 500,
     "Sweep a sector, reveal threats, and keep the roads open.", ("scout",)),
    ("patrol_near_location", "Area Patrol", 550,
     "Patrol an important location and deter nearby enemy activity.", ("skirmisher",)),
    ("defend_location", "Defend Position", 750,
     "Hold a designated location against an expected attack.", ("front_line",)),
    ("recover_or_steal_mech", "Recover Lost Mech", 900,
     "Retrieve or seize a disabled mech before another force claims it.", ("recovery", "front_line")),
)


class MercenaryCampaign:
    """Own campaign-level personnel, funds, research, and contract choices."""

    STARTING_CASH = 1_000
    STARTING_HANGAR_LIMITS = {2: 5, 3: 1}
    STARTING_RESEARCH = {"lancer.type_a", "bastion"}

    def __init__(self, rng=None):
        self.rng = rng if rng is not None else random.Random()
        self.cash = self.STARTING_CASH
        # Limits are deliberately by class size. Research unlocks the chassis
        # a slot may field; acquiring/refitting individual assets comes later.
        self.hangarLimits = dict(self.STARTING_HANGAR_LIMITS)
        self.researchedMechs = set(self.STARTING_RESEARCH)
        self.pilots = self._create_starting_pilots()
        self.deployments = []
        self.missionOffers = self._generate_mission_offers()
        self.activeMission = None

    def _create_starting_pilots(self):
        """Create the six distinct pilots available at the beginning of a run."""
        pilots = []
        for _ in range(6):
            pilots.append(Pilot(generate_pilot_name(self.rng, [pilot.name for pilot in pilots])))
        return pilots

    def _generate_mission_offers(self):
        """Offer three different contracts, selected reproducibly from templates."""
        templates = self.rng.sample(MISSION_TEMPLATES, 3)
        return [
            CampaignMission(index, kind, title, payout, description, roles)
            for index, (kind, title, payout, description, roles) in enumerate(templates, start=1)
        ]

    @property
    def availablePilots(self):
        """Return living, non-MIA pilots who are not already deployed."""
        deployed = {deployment.pilot_name for deployment in self.deployments}
        return [
            pilot for pilot in self.pilots
            if pilot.status in {"Active", "RTB"} and pilot.name not in deployed
        ]

    def deployed_count(self, size):
        """Return how many class-size hangar slots are committed to deployment."""
        return sum(deployment.size == size for deployment in self.deployments)

    def can_deploy(self, mech_id, pilot_name):
        """Validate a proposed deployment without changing campaign state."""
        if mech_id not in self.researchedMechs:
            return False, f"{mech_id} has not been researched."
        try:
            mech = create_mech(mech_id)
        except ValueError as error:
            return False, str(error)
        if self.deployed_count(mech.size) >= self.hangarLimits.get(mech.size, 0):
            return False, f"No class {mech.size} hangar slots remain."
        if pilot_name not in {pilot.name for pilot in self.availablePilots}:
            return False, f"Pilot '{pilot_name}' is unavailable."
        return True, ""

    def deploy(self, mech_id, pilot_name):
        """Commit one available pilot and researched chassis to the next mission."""
        allowed, reason = self.can_deploy(mech_id, pilot_name)
        if not allowed:
            raise ValueError(reason)
        deployment = Deployment(pilot_name, mech_id, create_mech(mech_id).size)
        self.deployments.append(deployment)
        return deployment

    def recall(self, pilot_name):
        """Remove a planned deployment without changing pilot survival state."""
        for deployment in self.deployments:
            if deployment.pilot_name == pilot_name:
                self.deployments.remove(deployment)
                return True
        return False

    def accept_mission(self, mission_id):
        """Select one offered contract; map construction is a later campaign step."""
        for mission in self.missionOffers:
            if mission.mission_id == mission_id:
                self.activeMission = mission
                return mission
        raise ValueError(f"Unknown mission offer '{mission_id}'.")

    def adjust_cash(self, amount):
        """Apply a payment or expense, rejecting purchases the company cannot cover."""
        if self.cash + amount < 0:
            raise ValueError("The company cannot afford that expense.")
        self.cash += amount
        return self.cash

    def reconcile_pilots(self, mission_pilots):
        """Copy tactical pilot outcomes back after a future campaign mission.

        Tactical matches currently copy pilots when creating entities. This
        explicit boundary keeps campaign records stable until a mission-result
        handoff is added.
        """
        by_name = {pilot.name: pilot for pilot in self.pilots}
        for mission_pilot in mission_pilots:
            pilot = by_name.get(mission_pilot.name)
            if pilot is None:
                continue
            pilot.status = mission_pilot.status
            pilot.returned = mission_pilot.returned
            pilot.ejectionOutcome = mission_pilot.ejectionOutcome
            pilot.ejectionLocation = mission_pilot.ejectionLocation

