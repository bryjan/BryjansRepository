"""Direct-fire and launcher targeting commands."""

import math

from ..ui import tactical as pv

from .. import artillery, radar
from ..coordinates import get_coordinate_input
from .shared import read_nonempty


def fire(matchInfo, target=None):
    """Fire the selected weapon, optionally starting from a chosen target."""
    mech = matchInfo.pov
    if target is not None:
        # A deliberate target selection remains visible after this shot.
        mech.focusedEnemy = target
    gunList = mech.mechClass.gunList

    if not gunList:
        print("You have no weapons.")
        return

    default_guns = [weapon for weapon in gunList if weapon.defaultGun]
    if len(default_guns) != 1:
        print("Select a default weapon.")
        return gunMenu(matchInfo)
    gun = default_guns[0]

    if gun.isLauncher:
        return launcherFireMenu(matchInfo, gun, target)

    # The radar menu can pass one exact shared contact here. Ordinary 'f'
    # input keeps the quick-fire behavior of choosing the nearest contact.
    default_target = target if target is not None else nearestTrackedEnemy(matchInfo, mech)
    prompt = fireTargetPrompt(matchInfo, default_target, gun)
    if default_target is not None:
        printTargetingSummary(matchInfo, gun, default_target, "Default target")
        detail = radar.contact_details(mech, matchInfo, default_target)
        pv.printPOV(matchInfo, *detail["position"], command_text=prompt)
    else:
        pv.printPOV(matchInfo, *mech.pos, command_text=prompt)

    target_choice = chooseFireTarget(matchInfo, default_target, gun, promptDisplayed=True)
    if target_choice == "weapon":
        return gunMenu(matchInfo, default_target)
    if target_choice is None:
        return
    target_pos, aimed_limb = target_choice
    gun.shootAt(matchInfo, target_pos, aimed_limb)


def launcherFireMenu(matchInfo, launcher, target=None, fire_mission=None):
    """Choose a location for a delayed launcher shot without limb aiming."""
    mech = matchInfo.pov
    default_target = target if target is not None else nearestTrackedEnemy(matchInfo, mech)
    default_position = None
    if default_target is not None:
        detail = radar.contact_details(mech, matchInfo, default_target)
        default_position = detail["position"]
        print(
            f"Launcher target: {detail['classification']} at {default_position} "
            f"| distance {detail['distance']:.1f} tiles"
        )
        printLauncherProfile(matchInfo, mech, launcher, default_position)
        prompt = launcherFirePrompt(matchInfo, launcher, default_target, hasDefault=True)
    else:
        prompt = launcherFirePrompt(matchInfo, launcher, None)

    if fire_mission is not None:
        prompt += " | 'u' artillery unit"
        print(f"Fire mission: {mech.pilot.display_name} — {launcher.name}. Plot a shot for this squad's turn.")

    def launch(position):
        return fire_mission(matchInfo, mech, launcher, position) if fire_mission is not None else launcher.launchAt(matchInfo, position)

    def reopen(selected_target):
        if fire_mission is not None:
            return launcherFireMenu(matchInfo, launcher, selected_target, fire_mission=fire_mission)
        return launcherFireMenu(matchInfo, launcher, selected_target)

    view_position = default_position if default_position is not None else mech.pos
    pv.printPOV(matchInfo, *view_position, command_text=prompt)
    raw_choice = input("Launch: ").strip()
    if raw_choice == "L":
        position = predictLauncherLead(matchInfo, launcher, default_target)
        if position is None:
            print("Auto lead needs a visually confirmed or fully identified radar target.")
            return
        print(f"Auto lead projects the target at {position} when the shell lands.")
        choice = "auto_lead"
    else:
        choice = raw_choice.lower()
    if choice in ("", "f") and default_position is not None:
        return launch(default_position)
    if choice == "u" and fire_mission is not None:
        return "switch_artillery"
    if choice == "t":
        selected_target = chooseLauncherTrackedContact(matchInfo)
        if selected_target is None:
            return
        # Reopen the complete launcher menu with this contact as its default.
        # This keeps lead offset and ammunition selection available after
        # changing target instead of forcing an immediate launch confirmation.
        return reopen(selected_target)
    if choice == "c":
        position = get_coordinate_input(matchInfo, "Enter launch coordinates")
        if position == "x":
            return
    elif choice == "l":
        position = list(mech.lastFiredAt) if mech.lastFiredAt is not None else None
        if position is None:
            print("No previous firing location.")
            return
    elif choice == "o":
        base_position = default_position or chooseLauncherTrackedTarget(matchInfo)
        if base_position is None:
            return
        position = getLauncherLeadOffset(matchInfo, base_position)
    elif choice == "a":
        if chooseLauncherAmmo(launcher):
            return reopen(target)
        return
    elif choice == "w":
        if fire_mission is not None:
            return "switch_launcher"
        return gunMenu(matchInfo, target)
    elif choice == "auto_lead":
        pass
    elif choice in ("", "f", "x"):
        return
    else:
        print("Choose a listed launcher option.")
        return

    if position is not None and printLauncherProfile(matchInfo, mech, launcher, position) is not None:
        pv.printPOV(
            matchInfo, *position,
            command_text="Launch: 'Enter' or 'f' confirm | 'x' cancel",
        )
        confirm = input("Press 'Enter' or 'f' to launch, or 'x' to cancel: ").strip().lower()
        if confirm in ("", "f"):
            return launch(position)


def launcherFirePrompt(matchInfo, launcher, target=None, hasDefault=False):
    """Return only launcher choices that are valid for the current sensors."""
    prompt = "Launch: "
    if hasDefault:
        prompt += "'Enter' or 'f' default | "
    prompt += "'a' ammo | 't' tracked target | "
    if launcherAutoLeadAvailable(matchInfo, target):
        # Uppercase L is deliberately distinct from lowercase l (last shot).
        prompt += "'L' auto lead | "
    return prompt + "'o' lead offset | 'c' coordinates | 'l' last location | 'w' weapon | 'x' cancel"


def predictLauncherLead(matchInfo, launcher, target):
    """Project a fully resolved contact forward by the shell's travel time."""
    return artillery.predict_launcher_lead(matchInfo, launcher, target, matchInfo.pov)


def launcherAutoLeadAvailable(matchInfo, target):
    """Require team sight or the highest radar ID before predicting movement."""
    return artillery.auto_lead_available(matchInfo, matchInfo.pov, target)


def printLauncherProfile(matchInfo, mech, launcher, position):
    """Display the launcher band that will govern a shot at ``position``."""
    distance = math.dist(mech.pos, position)
    range_bonus = launcher.launcher_range_bonus(matchInfo, mech)
    profile = launcher.launcher_profile(distance, matchInfo, mech)
    if profile is None:
        far_range = launcher.selected_ammo.rangeBands["far"][0] + range_bonus
        print(f"Out of range: far profile reaches {far_range} tiles.")
        return None

    ammo = launcher.selected_ammo
    damage = max(0, launcher.dmg + ammo.damageModifier - profile["damage_falloff"])
    charges = "unlimited" if ammo.charges is None else f"{ammo.charges}/{ammo.maxCharges}"
    details = (
        f"{ammo.name} ({ammo.payload}) | distance {distance:.1f} tiles | "
        f"{profile['name'].capitalize()} profile — range ≤{profile['max_range']} | "
        f"scatter {profile['inaccuracy']} tile(s) | impact in {profile['turns']} turn(s) | "
    )
    if ammo.payload == "explosive":
        details += f"damage {damage} | "
    elevation = f" | mountain range +{range_bonus}" if range_bonus else ""
    print(details + f"rounds {charges}{elevation}")
    return profile


def chooseLauncherAmmo(launcher):
    """Select which projectile type supplies this launcher's range profile."""
    for index, ammo in enumerate(launcher.ammoTypes, start=1):
        charges = "unlimited" if ammo.charges is None else f"{ammo.charges}/{ammo.maxCharges}"
        loaded = " (loaded)" if index - 1 == launcher.selectedAmmoIndex else ""
        print(f"'{index}' {ammo.name} — {ammo.payload}, rounds {charges}{loaded}")
    selection = input("Ammo: ").strip()
    if not selection.isdigit() or not 1 <= int(selection) <= len(launcher.ammoTypes):
        print("Choose a listed ammunition number.")
        return False
    launcher.select_ammo(int(selection) - 1)
    return True


def getLauncherLeadOffset(matchInfo, basePosition):
    """Apply one signed X/Y lead offset to a remembered target position."""
    while True:
        raw_offset = input(
            "Lead offset 'x,y' (positive X east, positive Y north; 'x' to cancel): "
        ).strip().lower()
        if raw_offset == "x":
            return None
        try:
            x_offset, y_offset = (int(value.strip()) for value in raw_offset.split(","))
        except ValueError:
            print("Enter two signed whole numbers separated by one comma.")
            continue

        position = [basePosition[0] + x_offset, basePosition[1] + y_offset]
        if 1 <= position[0] < matchInfo.mapWidth - 1 and 1 <= position[1] < matchInfo.mapHeight - 1:
            return position
        print("The offset must place the impact inside the map border.")


def chooseLauncherTrackedContact(matchInfo):
    """Select a remembered or visible contact for a launcher target menu."""
    mech = matchInfo.pov
    if not mech.trackedEnemies:
        print("No enemy mechs are currently tracked.")
        return None
    if len(mech.trackedEnemies) == 1:
        return mech.trackedEnemies[0]

    for index, enemy in enumerate(mech.trackedEnemies, start=1):
        detail = radar.contact_details(mech, matchInfo, enemy)
        print(
            f"'{index}' {detail['classification']} at {detail['position']} "
            f"| distance {detail['distance']:.1f} tiles"
        )
    selection = read_nonempty("Launch target: ")
    if not selection.isdigit() or not 1 <= int(selection) <= len(mech.trackedEnemies):
        print("Choose a listed target number.")
        return None
    selected_target = mech.trackedEnemies[int(selection) - 1]
    mech.focusedEnemy = selected_target
    return selected_target


def chooseLauncherTrackedTarget(matchInfo):
    """Return the selected contact's position for lead-offset calculations."""
    target = chooseLauncherTrackedContact(matchInfo)
    if target is None:
        return None
    return radar.contact_position(matchInfo.pov, target)


def nearestTrackedEnemy(matchInfo, mech):
    """Return the closest tracked enemy, or ``None`` when no contact exists."""
    if not mech.trackedEnemies:
        return None
    return min(
        mech.trackedEnemies,
        key=lambda enemy: math.dist(mech.pos, radar.contact_position(mech, enemy)),
    )


def fireTargetPrompt(matchInfo, defaultTarget=None, weapon=None):
    """Return the direct-fire choices that belong in the tactical command bar."""
    if defaultTarget is None:
        return "Fire target: 'w' weapon | 't' tracked enemy | 'l' last location | 'c' coordinates | 'x' cancel"
    can_aim = radar.can_aim_at_contact(matchInfo.pov, matchInfo, defaultTarget)
    prompt = "Press 'Enter' or 'f' to fire."
    if can_aim:
        prompt += f" 'a' aim limb ({aimingCostLabel(weapon)}) |"
    return prompt + " 'w' weapon | 't' tracked enemy | 'l' last location | 'c' coordinates | 'x' cancel"


def chooseFireTarget(matchInfo, defaultTarget=None, weapon=None, promptDisplayed=False):
    """Confirm the default target or choose another firing location."""
    mech = matchInfo.pov
    if defaultTarget is not None:
        can_aim = radar.can_aim_at_contact(mech, matchInfo, defaultTarget)
        if not promptDisplayed:
            print(fireTargetPrompt(matchInfo, defaultTarget, weapon))
        choice = input("Target: ").strip().lower()
        if choice in ("", "f"):
            return radar.contact_position(mech, defaultTarget), None
        if choice == "a" and can_aim:
            aimed_limb = chooseAimedLimb(defaultTarget)
            return None if aimed_limb is None else (radar.contact_position(mech, defaultTarget), aimed_limb)
        if choice == "a":
            print("Limb aiming requires direct visual contact or a fully identified radar return.")
            return None
    else:
        if not promptDisplayed:
            print(fireTargetPrompt(matchInfo, weapon=weapon))
        choice = read_nonempty("Target: ").lower()

    if choice == "x":
        return None
    if choice == "w":
        return "weapon"
    if choice == "c":
        target = get_coordinate_input(matchInfo, "Enter coordinates to shoot at")
        return None if target == "x" else (target, None)
    if choice == "l":
        if mech.lastFiredAt is None:
            print("No previous firing location.")
            return None
        target = next(
            (
                enemy
                for enemy in mech.trackedEnemies
                if radar.contact_position(mech, enemy) == mech.lastFiredAt
            ),
            None,
        )
        return chooseFireTarget(matchInfo, target, weapon) if target is not None else (list(mech.lastFiredAt), None)
    if choice not in ("t", "v"):
        print("Choose 't', 'l', 'c', or 'x'.")
        return None
    selected_target = chooseTrackedContact(matchInfo)
    if selected_target is None:
        return None
    # As with launchers, retain the selected contact and reopen the full
    # targeting menu so weapon switching and limb aiming stay available.
    detail = radar.contact_details(mech, matchInfo, selected_target)
    pv.printPOV(
        matchInfo, *detail["position"],
        command_text=fireTargetPrompt(matchInfo, selected_target, weapon),
    )
    return chooseFireTarget(matchInfo, selected_target, weapon, promptDisplayed=True)


def chooseTrackedContact(matchInfo):
    """Select a tracked enemy while retaining it as an entity reference."""
    mech = matchInfo.pov
    if not mech.trackedEnemies:
        print("No enemy mechs are currently tracked.")
        return None
    if len(mech.trackedEnemies) == 1:
        return mech.trackedEnemies[0]

    for index, enemy in enumerate(mech.trackedEnemies, start=1):
        detail = radar.contact_details(mech, matchInfo, enemy)
        print(
            f"'{index}' {detail['classification']} at {detail['position']} "
            f"| distance {detail['distance']:.1f} tiles"
        )
    selection = read_nonempty("Tracked target: ")
    if not selection.isdigit() or not 1 <= int(selection) <= len(mech.trackedEnemies):
        print("Choose a listed target number.")
        return None
    selected_target = mech.trackedEnemies[int(selection) - 1]
    mech.focusedEnemy = selected_target
    return selected_target


def printTargetingSummary(matchInfo, weapon, target, label="Target"):
    """Print range and, when sensors identify it, the direct-fire chance."""
    observer = matchInfo.pov
    detail = radar.contact_details(observer, matchInfo, target)
    print(
        f"{label}: {detail['classification']} at {detail['position']} "
        f"| distance {detail['distance']:.1f} tiles"
    )

    # Exact target size is required for the size modifier. Visual contact or
    # radar level 3 supplies it; lower-grade returns deliberately do not.
    if weapon is None or weapon.isLauncher or not radar.can_aim_at_contact(observer, matchInfo, target):
        return
    if weapon.maxRange is not None and detail["distance"] > weapon.maxRange:
        print(f"Out of range: {weapon.name} reaches {weapon.maxRange} tiles.")
        return

    low, high = weapon.hit_chance_range(matchInfo, observer, target, detail["position"])
    chance = f"{high}%" if low == high else f"{low}–{high}% (movement-dependent)"
    print(f"Hit chance: {chance}")


def aimingCostLabel(weapon):
    """Describe the selected weapon's additional AP cost for limb targeting."""
    return "free" if weapon is not None and weapon.isMelee else "+1 AP"


def chooseAimedLimb(target):
    """Let the player select a live target part for the current weapon."""
    for index, limb in enumerate(target.mechClass.limbList, start=1):
        print(
            f"{index}. {limb.name} — armor {limb.armor}/{limb.startingArmor}, "
            f"HP {limb.hp}/{limb.startingHP}"
        )
    selection = read_nonempty("Aim at limb ('x' to cancel): ").lower()
    if selection == "x":
        return None
    if not selection.isdigit() or not 1 <= int(selection) <= len(target.mechClass.limbList):
        print("Choose a listed limb number.")
        return None
    return target.mechClass.limbList[int(selection) - 1]


def gunMenu(matchInfo, target=None):
    """Select a default weapon, preserving a radar-selected target if present."""
    mech = matchInfo.pov
    gun_list = mech.mechClass.gunList

    if len(gun_list) == 1:
        gun_list[0].defaultGun = True
        print(gun_list[0].printShortDesc())
        print("You only have one weapon. It is set as the default for 'f'.")
        return fire(matchInfo, target) if target is not None else None
    if not gun_list:
        print("You have no weapons.")
        return

    menu_width = max(len(limb.printShortDesc()) for limb in gun_list) + 4
    menu_divider = "-" * menu_width
    print("Select the default weapon used by 'f'.")
    for index, limb in enumerate(gun_list, start=1):
        print(menu_divider)
        print(f"'{index}' {limb.printShortDesc()}")
    print(menu_divider)

    while True:
        player_input = read_nonempty("Choose weapon number or 'x' to cancel: ").lower()
        if player_input == "x":
            return
        if not player_input.isdigit() or not 1 <= int(player_input) <= len(gun_list):
            print("Choose a listed weapon number or 'x'.")
            continue

        for limb in gun_list:
            limb.defaultGun = False
        selected = gun_list[int(player_input) - 1]
        selected.defaultGun = True
        print(f"{selected.name} is now the default for 'f'.")
        return fire(matchInfo, target) if target is not None else None
