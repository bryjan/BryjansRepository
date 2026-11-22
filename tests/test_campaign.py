import random
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

from mechgame.campaign import CampaignMission, MISSION_TEMPLATES, MercenaryCampaign


class MercenaryCampaignTests(unittest.TestCase):
    def setUp(self):
        self.campaign = MercenaryCampaign(random.Random(4))

    def test_campaign_starts_with_six_unique_pilots_and_expected_resources(self):
        self.assertEqual(self.campaign.cash, 1_000)
        self.assertEqual(self.campaign.hangarLimits, {2: 5, 3: 1})
        self.assertEqual(len(self.campaign.pilots), 6)
        self.assertEqual(len({pilot.name for pilot in self.campaign.pilots}), 6)
        self.assertTrue(all(pilot.nickname is None for pilot in self.campaign.pilots))
        self.assertEqual(self.campaign.researchedMechs, {"lancer.type_a", "bastion"})

    def test_campaign_offers_three_distinct_missions(self):
        self.assertEqual(len(self.campaign.missionOffers), 3)
        self.assertEqual(len({offer.kind for offer in self.campaign.missionOffers}), 3)

    def test_player_contract_pool_excludes_patrols_and_defines_new_objectives(self):
        templates = {template[0]: template for template in MISSION_TEMPLATES}

        self.assertNotIn("patrol_map", templates)
        self.assertNotIn("patrol_near_location", templates)
        self.assertEqual(templates["diversion"][5:7], ("deal_damage", 120))
        self.assertEqual(templates["locate_enemy_base"][5:7], ("visual_contact", 1))
        self.assertEqual(templates["sabotage"][5:7], ("hold_position", 1))
        self.assertEqual(templates["sabotage"][7], ("tactical_location", "suburbs"))

    def test_diversion_scales_with_company_progress_and_pays_by_damage_ratio(self):
        baseline = self.campaign.diversion_damage_requirement()
        self.assertEqual(baseline, 120)

        self.campaign.researchedMechs.add("lancer.pathfinder")
        self.assertGreater(self.campaign.diversion_damage_requirement(), baseline)
        self.campaign.hangarLimits[3] += 1
        self.assertGreater(self.campaign.diversion_damage_requirement(), baseline)
        self.assertGreater(
            self.campaign.diversion_damage_requirement(enemy_presence=1.5),
            self.campaign.diversion_damage_requirement(),
        )

        mission = CampaignMission(1, "diversion", "Diversion", 700, "", (), "deal_damage", 120)
        self.assertEqual(mission.diversion_payout(60), 350)
        self.assertEqual(mission.diversion_payout(120), 700)
        self.assertEqual(mission.diversion_payout(180), 1_050)

    def test_sabotage_contracts_generate_one_to_three_targets_with_per_target_rewards(self):
        sabotage = next(template for template in MISSION_TEMPLATES if template[0] == "sabotage")
        alternatives = [template for template in MISSION_TEMPLATES if template[0] != "sabotage"][:2]
        self.campaign.rng = SimpleNamespace(
            sample=lambda *_: [sabotage, *alternatives],
            randint=lambda *_: 3,
        )

        offer = next(mission for mission in self.campaign._generate_mission_offers() if mission.kind == "sabotage")

        self.assertEqual(offer.objective_value, 3)
        self.assertEqual(offer.reward_per_target, 300)
        self.assertEqual(offer.payout, 900)

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

    def test_campaign_displays_a_callsign_without_changing_legal_identity(self):
        pilot = self.campaign.pilots[0]
        deployment = self.campaign.deploy("lancer.type_a", pilot.name)
        pilot.assign_callsign("Viper")

        self.assertEqual(self.campaign.display_name_for(pilot.name), "Viper")
        self.assertEqual(deployment.pilot_name, pilot.name)

    def test_save_load_preserves_pilots_traits_skills_and_campaign_state(self):
        pilot = self.campaign.pilots[0]
        pilot.assign_nickname("Sparrow")
        pilot.assign_callsign("Viper")
        pilot.toggle_nickname_visibility()
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
        self.assertEqual(loaded_pilot.nickname, "Sparrow")
        self.assertFalse(loaded_pilot.nicknameVisible)
        self.assertEqual(loaded_pilot.callsign, "Viper")
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
