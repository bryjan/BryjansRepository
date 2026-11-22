"""The small pre-match menu used to start a playable skirmish."""

from dataclasses import dataclass, field
import textwrap

from ..campaign import MercenaryCampaign
from ..world import (
    CUSTOM_MAP_PRESET,
    DEFAULT_MAP_PRESET,
    DEFAULT_TERRAIN_ENABLED,
    GENERATABLE_TERRAINS,
    MAP_PRESETS,
    get_map_preset,
)
from .tactical import (
    DEFAULT_DISPLAY_HEIGHT,
    DEFAULT_DISPLAY_WIDTH,
    MIN_DISPLAY_HEIGHT,
    tactical_dimensions,
)

MENU_MIN_INNER_WIDTH = 40


@dataclass
class DisplaySettings:
    """Display and map-generation choices collected before a match begins."""

    display_width: int = DEFAULT_DISPLAY_WIDTH
    display_height: int = DEFAULT_DISPLAY_HEIGHT
    terrain_enabled: dict = field(default_factory=lambda: dict(DEFAULT_TERRAIN_ENABLED))
    map_preset: str = DEFAULT_MAP_PRESET


def _frame_lines(lines, settings):
    """Build a fixed-size menu frame from the selected display dimensions."""
    # The start menu fills the same complete terminal frame as tactical play.
    width = max(MENU_MIN_INNER_WIDTH, settings.display_width - 4)
    content = []
    for line in lines:
        content.extend(textwrap.wrap(line, width=width) or [""])
    height = max(settings.display_height - 2, len(content))
    divider = "+" + ("-" * (width + 2)) + "+"
    return [
        divider,
        *(f"| {line:<{width}} |" for line in content),
        *(f"| {'':<{width}} |" for _ in range(height - len(content))),
        divider,
    ]


def _frame(lines, settings):
    """Print a consistently sized pre-match menu frame."""
    for line in _frame_lines(lines, settings):
        print(line)


def _read_display_size(dimension, current, other_dimension):
    """Prompt for one full-frame dimension, retaining the old value on cancel."""
    while True:
        value = input(
            f"{dimension} (whole number; 'x' to cancel): "
        ).strip().lower()
        if value in ("", "x"):
            return current
        if value.isdigit():
            try:
                dimensions = (
                    (int(value), other_dimension)
                    if dimension == "Display width" else (other_dimension, int(value))
                )
                tactical_dimensions(*dimensions)
                return int(value)
            except ValueError as error:
                print(error)
                continue
        print("Enter a whole number or 'x' to cancel.")


def options_menu(settings):
    """Open display and terrain-generation settings before a match begins."""
    while True:
        _frame([
            "OPTIONS",
            "'d' Display size",
            f"'p' Map preset: {_preset_name(settings.map_preset)}",
            "'m' Map tile generation (custom toggles)",
            "'x' Back",
        ], settings)
        choice = input("Options: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "d":
            display_options_menu(settings)
        elif choice == "p":
            preset_options_menu(settings)
        elif choice == "m":
            terrain_options_menu(settings)
        else:
            print("Choose 'd', 'p', 'm', or 'x'.")


def _preset_name(preset_key):
    """Return the menu label for a named preset or a hand-tuned map."""
    if preset_key == CUSTOM_MAP_PRESET:
        return "Custom"
    return get_map_preset(preset_key).name


def _apply_preset(settings, preset):
    """Replace custom terrain choices with one complete preset configuration."""
    settings.map_preset = preset.key
    settings.terrain_enabled = preset.terrain_options()


def preset_options_menu(settings):
    """Choose a cohesive terrain profile without touching match content."""
    while True:
        lines = ["MAP PRESETS", "Presets affect terrain generation only."]
        for index, preset in enumerate(MAP_PRESETS, start=1):
            current = " (CURRENT)" if settings.map_preset == preset.key else ""
            lines.append(f"'{index}' {preset.name}{current}")
            lines.append(f"    {preset.description}")
        lines.extend(["", "Choosing a preset replaces custom tile selections.", "'x' Back"])
        _frame(lines, settings)
        choice = input("Map preset: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(MAP_PRESETS):
            _apply_preset(settings, MAP_PRESETS[int(choice) - 1])
            return
        print(f"Choose a number from 1 to {len(MAP_PRESETS)}, or 'x'.")


def display_options_menu(settings):
    """Change the complete terminal frame used by menus and tactical play."""
    while True:
        _frame([
            "DISPLAY SIZE",
            f"'w' Display width:  {settings.display_width}",
            f"'h' Display height: {settings.display_height}",
            "Width must be 3 more than a multiple of 4; height must be even.",
            "'x' Back",
        ], settings)
        choice = input("Display: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "w":
            settings.display_width = _read_display_size(
                "Display width", settings.display_width, settings.display_height
            )
        elif choice == "h":
            settings.display_height = _read_display_size(
                "Display height", settings.display_height, settings.display_width
            )
        else:
            print("Choose 'w', 'h', or 'x'.")


def terrain_options_menu(settings):
    """Toggle optional terrain generators without affecting structural tiles."""
    while True:
        lines = [
            "MAP TILE GENERATION",
            f"Current style: {_preset_name(settings.map_preset)}",
            "Changing a tile selection makes this map Custom.",
            "Custom maps use Temperate Frontier generation frequencies.",
        ]
        for index, terrain in enumerate(GENERATABLE_TERRAINS, start=1):
            status = "ON" if settings.terrain_enabled[terrain] else "OFF"
            lines.append(f"'{index}' {terrain.title()}: {status}")
        lines.extend(["", "Plains and borders are always generated.", "'x' Back"])
        _frame(lines, settings)
        choice = input("Map tiles: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(GENERATABLE_TERRAINS):
            terrain = GENERATABLE_TERRAINS[int(choice) - 1]
            settings.terrain_enabled[terrain] = not settings.terrain_enabled[terrain]
            settings.map_preset = CUSTOM_MAP_PRESET
        else:
            print(f"Choose a number from 1 to {len(GENERATABLE_TERRAINS)}, or 'x'.")


def _campaign_lines(campaign):
    """Build the concise company status and contract view for Mercenary Mode."""
    lines = [
        "MERCENARY MODE",
        f"Cash: {campaign.cash:,} credits",
        "Hangar: " + ", ".join(
            f"Class {size}: {campaign.deployed_count(size)}/{limit} deployed"
            for size, limit in sorted(campaign.hangarLimits.items())
        ),
        f"Pilots available: {len(campaign.availablePilots)}/{len(campaign.pilots)}",
        "Research: " + ", ".join(sorted(campaign.researchedMechs)),
        "",
        "CONTRACTS",
    ]
    for offer in campaign.missionOffers:
        active = " (ACTIVE)" if offer is campaign.activeMission else ""
        role_text = ", ".join(offer.required_roles) or "general"
        payout = f"{offer.payout:,} credits"
        if offer.reward_per_target:
            payout = f"{offer.reward_per_target:,}/target + threat pay, {offer.payout:,} maximum"
        enemy_force = (
            f"Enemy force: {offer.enemy_combat_force}"
            if offer.enemy_force_revealed else "Enemy force: unknown"
        )
        lines.extend([
            f"'{offer.mission_id}' {offer.title} — {payout}{active}",
            f"    {offer.description} Needed: {role_text}. {enemy_force}",
        ])
    lines.extend(["", "'d' Deploy roster", "'p' Pilot identities", "'x' Back"])
    return lines


def deployment_menu(settings, campaign):
    """Let the player assign researched chassis and available pilots to slots."""
    while True:
        lines = ["DEPLOYMENT", "Current roster:"]
        if campaign.deployments:
            lines.extend(
                f"  {campaign.display_name_for(deployment.pilot_name)}: "
                f"{deployment.mech_id} (class {deployment.size})"
                for deployment in campaign.deployments
            )
        else:
            lines.append("  No mechs assigned.")
        lines.extend(["", "'a' Assign a mech", "'r' Recall a pilot", "'x' Back"])
        _frame(lines, settings)
        choice = input("Deployment: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "a":
            available = campaign.availablePilots
            chassis = sorted(campaign.researchedMechs)
            if not available:
                print("No pilots are available.")
                continue
            print("Chassis: " + ", ".join(f"{index + 1}) {mech_id}" for index, mech_id in enumerate(chassis)))
            print("Pilots: " + ", ".join(f"{index + 1}) {pilot.display_name}" for index, pilot in enumerate(available)))
            mech_choice = input("Chassis number ('x' cancel): ").strip().lower()
            pilot_choice = input("Pilot number ('x' cancel): ").strip().lower()
            if mech_choice == "x" or pilot_choice == "x":
                continue
            if not mech_choice.isdigit() or not pilot_choice.isdigit():
                print("Choose numbered chassis and pilot entries.")
                continue
            mech_index, pilot_index = int(mech_choice) - 1, int(pilot_choice) - 1
            if not (0 <= mech_index < len(chassis) and 0 <= pilot_index < len(available)):
                print("Choose numbered chassis and pilot entries.")
                continue
            try:
                campaign.deploy(chassis[mech_index], available[pilot_index].name)
            except ValueError as error:
                print(error)
            else:
                campaign.save()
        elif choice == "r":
            name = input("Pilot name to recall ('x' cancel): ").strip()
            if name.lower() != "x":
                if campaign.recall(name):
                    campaign.save()
                else:
                    print("That pilot has no assigned mech.")
        else:
            print("Choose 'a', 'r', or 'x'.")


def pilot_identity_menu(settings, campaign):
    """Assign legal names/callsigns and toggle display of earned nicknames."""
    while True:
        lines = ["PILOT IDENTITIES"]
        for index, pilot in enumerate(campaign.pilots, start=1):
            nickname = pilot.nickname or "—"
            nickname_state = "shown" if pilot.nicknameVisible else "hidden"
            callsign = pilot.callsign or "—"
            lines.append(
                f"'{index}' {pilot.display_name} | name: {pilot.name} | "
                f"nickname: {nickname} ({nickname_state}) | callsign: {callsign}"
            )
        lines.extend(["", "Choose a pilot to edit.", "'x' Back"])
        _frame(lines, settings)
        choice = input("Pilot: ").strip().lower()
        if choice in ("", "x"):
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(campaign.pilots):
            print("Choose a numbered pilot or 'x'.")
            continue
        pilot = campaign.pilots[int(choice) - 1]
        action = input("Edit: 'n' name | 'c' callsign | 't' nickname display | 'x' cancel: ").strip().lower()
        if action in ("", "x"):
            continue
        try:
            if action == "n":
                name = input(f"Name [{pilot.name}] ('Enter' keep): ").strip()
                if name:
                    pilot.assign_name(name)
            elif action == "c":
                callsign = input(f"Callsign [{pilot.callsign or '—'}] ('Enter' keep, '-' clear): ").strip()
                if callsign == "-":
                    pilot.assign_callsign(None)
                elif callsign:
                    pilot.assign_callsign(callsign)
            elif action == "t":
                if pilot.nickname is None:
                    print("This pilot has not earned a nickname yet.")
                    continue
                pilot.toggle_nickname_visibility()
            else:
                print("Choose 'n', 'c', 't', or 'x'.")
                continue
        except ValueError as error:
            print(error)
            continue
        campaign.save()


def mercenary_menu(settings, campaign):
    """Show the persistent company layer and allow contract selection."""
    while True:
        _frame(_campaign_lines(campaign), settings)
        choice = input("Mercenary Mode: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "d":
            deployment_menu(settings, campaign)
            continue
        if choice == "p":
            pilot_identity_menu(settings, campaign)
            continue
        if choice.isdigit():
            try:
                offer = campaign.accept_mission(int(choice))
            except ValueError:
                print("Choose one of the listed contracts, 'd', or 'x'.")
            else:
                campaign.save()
                print(f"Contract accepted: {offer.title}. Build your roster before deployment.")
            continue
        print("Choose a contract number, 'd', 'p', or 'x'.")


def start_menu(settings=None, campaign=None):
    """Return chosen settings when Skirmish starts, or ``None`` when quitting."""
    settings = settings or DisplaySettings()
    campaign = campaign or MercenaryCampaign()
    while True:
        _frame([
            "ASCII MECH GAME",
            "",
            "'s' Skirmish",
            "'m' Mercenary Mode",
            "'o' Options",
            "'q' Quit",
        ], settings)
        choice = input("Select: ").strip().lower()
        if choice == "s":
            return settings
        elif choice == "m":
            mercenary_menu(settings, campaign)
        elif choice == "o":
            options_menu(settings)
        elif choice in ("", "q", "x"):
            return None
        else:
            print("Choose 's', 'm', 'o', or 'q'.")
