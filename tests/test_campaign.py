import random
import unittest

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
