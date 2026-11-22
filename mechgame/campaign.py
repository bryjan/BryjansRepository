"""Persistent Mercenary Mode state, independent of one-off skirmishes.

The campaign deliberately stores durable strategic information only: money,
research, pilot availability, hangar limits, chosen deployments, and mission
offers. Tactical match construction and post-mission salvage are future work;
keeping them outside this module prevents a contract from mutating skirmish
state before a battle actually begins.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random

from .catalog import create_mech
from .entities import Pilot
from .names import generate_pilot_name

__all__ = ["CampaignMission", "Deployment", "RecoveredMech", "MercenaryCampaign"]

SAVE_VERSION = 1
DEFAULT_SAVE_PATH = Path("savegames") / "mercenary_campaign.json"


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


@dataclass(frozen=True)
class RecoveredMech:
    """An abandoned chassis secured or left behind after a campaign mission."""

    mech_id: str
    size: int
    recovery_state: str
    location: tuple[int, int] | None = None


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
    ("recover_or_steal_mech", "Recover Stranded Mech", 900,
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
        self.recoveredMechs = []
        self.leftBehindMechs = []
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
            pilot.traits = list(getattr(mission_pilot, "traits", []))
            pilot.skills = dict(getattr(mission_pilot, "skills", {}))

    @staticmethod
    def _mech_recovery_record(mech, recovery_state):
        """Convert a tactical abandoned entity into safe campaign data."""
        mech_class = mech.mechClass
        return RecoveredMech(
            getattr(mech_class, "catalogId", getattr(mech_class, "name", "unknown")),
            mech_class.size,
            recovery_state,
            tuple(mech.pos),
        )

    def resolve_match_recovery(self, match):
        """Resolve evacuees and abandoned chassis after one campaign battle.

        Clearing all enemy forces makes the field safe: every evading pilot
        returns and every abandoned chassis is secured, including enemy units.
        If hostile forces remain, both pilot escape and chassis recovery use a
        base 50 percent roll. Pilots who fail remain ``Evading`` at their last
        recorded location for a later pilot-recovery mission.
        """
        field_clear = len(match.operational_teams()) <= 1
        mission_pilots = list(match.ejectedPilots) + list(match.killedPilots)
        for pilot in mission_pilots:
            if pilot.status != "Evading":
                continue
            if field_clear or self.rng.randint(1, 100) <= 50:
                pilot.status = "RTB"
                pilot.returned = True
        self.reconcile_pilots(mission_pilots)

        recovered, left_behind = [], []
        for mech in match.abandonedMechs:
            if field_clear or self.rng.randint(1, 100) <= 50:
                recovered.append(self._mech_recovery_record(mech, "Recovered"))
            else:
                left_behind.append(self._mech_recovery_record(mech, "Left Behind"))
        self.recoveredMechs.extend(recovered)
        self.leftBehindMechs.extend(left_behind)
        return {
            "field_clear": field_clear,
            "returned_pilots": [pilot.name for pilot in mission_pilots if pilot.returned],
            "recovered_mechs": tuple(recovered),
            "left_behind_mechs": tuple(left_behind),
        }

    @staticmethod
    def _pilot_data(pilot):
        """Serialize pilot data explicitly so future fields stay intentional."""
        return {
            "name": pilot.name,
            "status": pilot.status,
            "returned": pilot.returned,
            "ejection_outcome": pilot.ejectionOutcome,
            "ejection_location": pilot.ejectionLocation,
            "traits": list(pilot.traits),
            "skills": dict(pilot.skills),
        }

    def to_dict(self):
        """Return a versioned, JSON-safe representation of this campaign."""
        active_id = self.activeMission.mission_id if self.activeMission else None
        return {
            "version": SAVE_VERSION,
            "cash": self.cash,
            "hangar_limits": self.hangarLimits,
            "researched_mechs": sorted(self.researchedMechs),
            "pilots": [self._pilot_data(pilot) for pilot in self.pilots],
            "deployments": [asdict(deployment) for deployment in self.deployments],
            "recovered_mechs": [asdict(mech) for mech in self.recoveredMechs],
            "left_behind_mechs": [asdict(mech) for mech in self.leftBehindMechs],
            "mission_offers": [asdict(mission) for mission in self.missionOffers],
            "active_mission_id": active_id,
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a campaign and tolerate fields absent from older saves."""
        if data.get("version") != SAVE_VERSION:
            raise ValueError("This campaign save uses an unsupported version.")
        campaign = cls.__new__(cls)
        campaign.rng = random.Random()
        campaign.cash = int(data["cash"])
        campaign.hangarLimits = {int(size): int(limit) for size, limit in data["hangar_limits"].items()}
        campaign.researchedMechs = set(data["researched_mechs"])
        campaign.pilots = []
        for pilot_data in data["pilots"]:
            pilot = Pilot(pilot_data["name"])
            pilot.status = pilot_data.get("status", "Active")
            pilot.returned = bool(pilot_data.get("returned", False))
            pilot.ejectionOutcome = pilot_data.get("ejection_outcome")
            location = pilot_data.get("ejection_location")
            pilot.ejectionLocation = tuple(location) if location is not None else None
            pilot.traits = list(pilot_data.get("traits", []))
            pilot.skills = dict(pilot_data.get("skills", {}))
            campaign.pilots.append(pilot)
        campaign.deployments = [Deployment(**deployment) for deployment in data.get("deployments", [])]
        campaign.recoveredMechs = [
            RecoveredMech(
                item["mech_id"], item["size"], item["recovery_state"],
                tuple(item["location"]) if item.get("location") is not None else None,
            )
            for item in data.get("recovered_mechs", [])
        ]
        campaign.leftBehindMechs = [
            RecoveredMech(
                item["mech_id"], item["size"], item["recovery_state"],
                tuple(item["location"]) if item.get("location") is not None else None,
            )
            for item in data.get("left_behind_mechs", [])
        ]
        campaign.missionOffers = [
            CampaignMission(
                item["mission_id"], item["kind"], item["title"], item["payout"],
                item["description"], tuple(item.get("required_roles", ())),
            )
            for item in data["mission_offers"]
        ]
        active_id = data.get("active_mission_id")
        campaign.activeMission = next(
            (mission for mission in campaign.missionOffers if mission.mission_id == active_id),
            None,
        )
        return campaign

    def save(self, path=DEFAULT_SAVE_PATH):
        """Atomically save campaign state so an interrupted write keeps the old save."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as save_file:
            json.dump(self.to_dict(), save_file, indent=2, sort_keys=True)
        temporary.replace(path)
        return path

    @classmethod
    def load(cls, path=DEFAULT_SAVE_PATH):
        """Load one saved campaign, reporting malformed files clearly to the caller."""
        path = Path(path)
        try:
            with path.open(encoding="utf-8") as save_file:
                return cls.from_dict(json.load(save_file))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Could not load campaign save '{path}'.") from error

    @classmethod
    def load_or_create(cls, path=DEFAULT_SAVE_PATH):
        """Continue a local campaign when possible, otherwise create a new one."""
        path = Path(path)
        return cls.load(path) if path.exists() else cls()

