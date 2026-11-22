import random
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

from mechgame.campaign import MercenaryCampaign


class MercenaryCampaignTests(unittest.TestCase):
    def setUp(self):
        self.campaign = MercenaryCampaign(random.Random(4))

    def test_campaign_starts_with_six_unique_pilots_and_expected_resources(self):
        self.assertEqual(self.campaign.cash, 1_000)
        self.assertEqual(self.campaign.hangarLimits, {2: 5, 3: 1})
        self.assertEqual(len(self.campaign.pilots), 6)
        self.assertEqual(len({pilot.name for pilot in self.campaign.pilots}), 6)
        self.assertEqual(self.campaign.researchedMechs, {"lancer.type_a", "bastion"})

    def test_campaign_offers_three_distinct_missions(self):
        self.assertEqual(len(self.campaign.missionOffers), 3)
        self.assertEqual(len({offer.kind for offer in self.campaign.missionOffers}), 3)

    def test_deploying_requires_research_an_available_pilot_and_a_class_slot(self):
        pilot_names = [pilot.name for pilot in self.campaign.pilots]
        self.campaign.deploy("lancer.type_a", pilot_names[0])
        self.assertEqual(self.campaign.deployed_count(2), 1)
        self.assertNotIn(pilot_names[0], {pilot.name for pilot in self.campaign.availablePilots})
        with self.assertRaisesRegex(ValueError, "not been researched"):
            self.campaign.deploy("lancer.pathfinder", pilot_names[1])

        for name in pilot_names[1:5]:
            self.campaign.deploy("lancer.type_a", name)
        with self.assertRaisesRegex(ValueError, "No class 2 hangar slots"):
            self.campaign.deploy("lancer.type_a", pilot_names[5])

    def test_accepting_an_offer_sets_the_active_contract(self):
        mission = self.campaign.accept_mission(2)
        self.assertIs(self.campaign.activeMission, mission)

    def test_save_load_preserves_pilots_traits_skills_and_campaign_state(self):
        pilot = self.campaign.pilots[0]
        pilot.traits = ["Steady"]
        pilot.skills = {"gunnery": 2, "scouting": 1}
        self.campaign.deploy("lancer.type_a", pilot.name)
        self.campaign.accept_mission(1)

        with TemporaryDirectory() as temporary_directory:
            save_path = Path(temporary_directory) / "campaign.json"
            self.campaign.save(save_path)
            loaded = MercenaryCampaign.load(save_path)

        loaded_pilot = next(item for item in loaded.pilots if item.name == pilot.name)
        self.assertEqual(loaded_pilot.traits, ["Steady"])
        self.assertEqual(loaded_pilot.skills, {"gunnery": 2, "scouting": 1})
        self.assertEqual(loaded.deployments, self.campaign.deployments)
        self.assertEqual(loaded.activeMission, self.campaign.activeMission)

    def test_clear_field_returns_evading_pilot_and_recovers_any_abandoned_mech(self):
        pilot = self.campaign.pilots[0]
        pilot.status = "Evading"
        pilot.ejectionLocation = (6, 7)
        abandoned_enemy = SimpleNamespace(
            mechClass=SimpleNamespace(catalogId="kestrel", size=3),
            pos=[6, 7],
        )
        match = SimpleNamespace(
            ejectedPilots=[pilot],
            killedPilots=[],
            abandonedMechs=[abandoned_enemy],
            operational_teams=lambda: [],
        )

        result = self.campaign.resolve_match_recovery(match)

        self.assertTrue(result["field_clear"])
        self.assertEqual(pilot.status, "RTB")
        self.assertEqual(self.campaign.recoveredMechs[0].mech_id, "kestrel")
        self.assertFalse(self.campaign.leftBehindMechs)

    def test_contested_field_can_leave_pilots_and_mechs_for_recovery(self):
        pilot = self.campaign.pilots[0]
        pilot.status = "Evading"
        abandoned_mech = SimpleNamespace(
            mechClass=SimpleNamespace(catalogId="lancer.type_a", size=2),
            pos=[4, 5],
        )
        match = SimpleNamespace(
            ejectedPilots=[pilot],
            killedPilots=[],
            abandonedMechs=[abandoned_mech],
            operational_teams=lambda: [object(), object()],
        )
        self.campaign.rng = SimpleNamespace(randint=lambda *_: 100)

        result = self.campaign.resolve_match_recovery(match)

        self.assertFalse(result["field_clear"])
        self.assertEqual(pilot.status, "Evading")
        self.assertEqual(len(self.campaign.leftBehindMechs), 1)
