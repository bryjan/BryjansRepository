import math

import printView as pv
from mechgame.coordinates import get_coordinate_input
from mechgame import radar


def _read_nonempty(prompt):
    """Read a trimmed command or menu value, rejecting blank input."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print()


def receive_input(matchInfo):
    """Read one player command and dispatch it to the relevant game action."""
    playerInput = _read_nonempty("Input: ").lower()

    match playerInput:
    
        case "?":
            return helpCommand(matchInfo)
        
        case "rep":
            return reportMenu(matchInfo)
        
        case "rep1":
            return unreadReportMenu(matchInfo)

        case "st" | "status":
            return statusPanel(matchInfo)

        case "sq" | "squad":
            return squadMenu(matchInfo)

        case "o" | "options":
            return optionsMenu(matchInfo)
        
        case "n" | "next":
            return matchInfo.nextMechinTeam()
        
        case "q" | "w" | "e" | "a" | "s" | "d" | "z" | "c":
            return matchInfo.pov.moveMech(matchInfo, playerInput)
        
        case "r" | "radar":
            return radarToggle(matchInfo)

        case "p":
            return matchInfo.pov.pulseRadar(matchInfo)

        case "ab" | "abilities":
            return abilityMenu(matchInfo)

        case "rd":
            return radarMenu(matchInfo)
        
        case "end":
            # This is the sole command that hands control to the next squad.
            matchInfo.turnEnded = True
            return
            
        case "look" | "l":
            return pv.lookAt(matchInfo)
        
        case "fire":
            return gunMenu(matchInfo)
        
        case "f" | "F":
            return fire(matchInfo)
        
        case _:
            print("Input not recognized. Try again.")
            return
    

def recieveInput(matchInfo):
    """Compatibility wrapper for the original misspelled command function."""
    return receive_input(matchInfo)


def radarToggle(matchInfo):
    """Toggle the active scanner, retaining a small helper for simple callers."""
    mech = matchInfo.pov
    if hasattr(mech, "toggleRadar"):
        return mech.toggleRadar(matchInfo)
    # Lightweight callers such as command tests may only supply a radar flag.
    mech.radarOn = not mech.radarOn


def statusPanel(matchInfo):
    """Open the normal tactical view as an explicit status reference."""
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Status: 'Enter' or 'x' return",
    )
    input("Status: ")


def abilityMenu(matchInfo):
    """Select and activate one of the active mech's hull-mounted abilities."""
    mech = matchInfo.pov
    abilities = mech.mechClass.hull.abilities
    if not abilities:
        print("This mech has no hull abilities.")
        return

    entries = [
        f"'{index}' {ability.short_description()}"
        for index, ability in enumerate(abilities, start=1)
    ]
    pv.printPOV(
        matchInfo, *mech.pos,
        command_text="Abilities: enter a listed number | 'x' cancel",
        right_panel=("HULL ABILITIES", entries),
    )
    choice = input("Ability ('x' to cancel): ").strip().lower()
    if choice in ("", "x"):
        return
    if not choice.isdigit() or not 1 <= int(choice) <= len(abilities):
        print("Choose a listed ability number or 'x'.")
        return

    ability = abilities[int(choice) - 1]
    direction = None
    if ability.requiresDirection:
        pv.printPOV(
            matchInfo, *mech.pos,
            command_text="Dash direction: 'q' 'w' 'e' 'a' 's' 'd' 'z' 'c' | 'x' cancel",
            right_panel=("HULL ABILITIES", entries),
        )
        direction = input("Dash direction ('q', 'w', 'e', 'a', 's', 'd', 'z', or 'c'; 'x' to cancel): ").strip().lower()
        if direction == "x":
            return
    ability.use(matchInfo, mech, direction)

def fire(matchInfo, target=None):
    """Fire the selected weapon, optionally starting from a chosen target."""
    mech = matchInfo.pov
    if target is not None:
        # A deliberate target selection remains visible after this shot.
        mech.focusedEnemy = target
    gunList = mech.mechClass.gunList

    if len(gunList) == 0:
        print("You have no weapons.")
        return
    
    defaultGuns = 0
    for limb in gunList:
        if limb.defaultGun == True:
            defaultGuns += 1
            gun = limb

    if defaultGuns < 1 or defaultGuns > 1:
        print("Select a default weapon.")
        return gunMenu(matchInfo)

    if gun.isLauncher:
        return launcherFireMenu(matchInfo, gun, target)
    
    # The radar menu can pass one exact shared contact here. Ordinary 'f'
    # input keeps the quick-fire behavior of choosing the nearest contact.
    defaultTarget = target if target is not None else nearestTrackedEnemy(matchInfo, mech)
    prompt = fireTargetPrompt(matchInfo, defaultTarget, gun)
    if defaultTarget is not None:
        printTargetingSummary(matchInfo, gun, defaultTarget, "Default target")
        detail = radar.contact_details(mech, matchInfo, defaultTarget)
        pv.printPOV(matchInfo, *detail["position"], command_text=prompt)
    else:
        pv.printPOV(matchInfo, *mech.pos, command_text=prompt)

    targetChoice = chooseFireTarget(matchInfo, defaultTarget, gun, promptDisplayed=True)
    if targetChoice == "weapon":
        return gunMenu(matchInfo, defaultTarget)
    if targetChoice is None:
        return
    targetPos, aimedLimb = targetChoice
    gun.shootAt(matchInfo, targetPos, aimedLimb)


def launcherFireMenu(matchInfo, launcher, target=None):
    """Choose a location for a delayed launcher shot without limb aiming."""
    mech = matchInfo.pov
    defaultTarget = target if target is not None else nearestTrackedEnemy(matchInfo, mech)
    defaultPosition = None
    if defaultTarget is not None:
        detail = radar.contact_details(mech, matchInfo, defaultTarget)
        defaultPosition = detail["position"]
        print(
            f"Launcher target: {detail['classification']} at {defaultPosition} "
            f"| distance {detail['distance']:.1f} tiles"
        )
        printLauncherProfile(mech, launcher, defaultPosition)
        prompt = launcherFirePrompt(matchInfo, launcher, defaultTarget, hasDefault=True)
    else:
        prompt = launcherFirePrompt(matchInfo, launcher, None)

    view_position = defaultPosition if defaultPosition is not None else mech.pos
    pv.printPOV(matchInfo, *view_position, command_text=prompt)
    raw_choice = input("Launch: ").strip()
    if raw_choice == "L":
        position = predictLauncherLead(matchInfo, launcher, defaultTarget)
        if position is None:
            print("Auto lead needs a visually confirmed or fully identified radar target.")
            return
        print(f"Auto lead projects the target at {position} when the shell lands.")
        choice = "auto_lead"
    else:
        choice = raw_choice.lower()
    if choice in ("", "f") and defaultPosition is not None:
        return launcher.launchAt(matchInfo, defaultPosition)
    if choice == "t":
        selectedTarget = chooseLauncherTrackedContact(matchInfo)
        if selectedTarget is None:
            return
        # Reopen the complete launcher menu with this contact as its default.
        # This keeps lead offset and ammunition selection available after
        # changing target instead of forcing an immediate launch confirmation.
        return launcherFireMenu(matchInfo, launcher, selectedTarget)
    elif choice == "c":
        position = get_coordinate_input(matchInfo, "Enter launch coordinates")
        if position == "x":
            return
    elif choice == "l":
        position = list(mech.lastFiredAt) if mech.lastFiredAt is not None else None
        if position is None:
            print("No previous firing location.")
            return
    elif choice == "o":
        basePosition = defaultPosition or chooseLauncherTrackedTarget(matchInfo)
        if basePosition is None:
            return
        position = getLauncherLeadOffset(matchInfo, basePosition)
    elif choice == "a":
        if chooseLauncherAmmo(launcher):
            return launcherFireMenu(matchInfo, launcher, target)
        return
    elif choice == "w":
        return gunMenu(matchInfo, target)
    elif choice == "auto_lead":
        pass
    elif choice in ("", "f", "x"):
        return
    else:
        print("Choose a listed launcher option.")
        return

    if position is not None:
        if printLauncherProfile(mech, launcher, position) is not None:
            pv.printPOV(
                matchInfo, *position,
                command_text="Launch: 'Enter' or 'f' confirm | 'x' cancel",
            )
            confirm = input("Press 'Enter' or 'f' to launch, or 'x' to cancel: ").strip().lower()
            if confirm in ("", "f"):
                launcher.launchAt(matchInfo, position)


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
    observer = matchInfo.pov
    if not launcherAutoLeadAvailable(matchInfo, target):
        return None

    detail = radar.contact_details(observer, matchInfo, target)
    visual_contact = radar.team_has_visual_contact(observer, target)
    position = list(target.pos) if visual_contact else list(detail["position"])
    if visual_contact:
        turn_start, speed = target.turnStartPos, target.speed
    else:
        memory = observer.team.radarContacts[target]
        turn_start, speed = memory["turn_start_pos"], memory["speed"]

    delta_x = position[0] - turn_start[0]
    delta_y = position[1] - turn_start[1]
    direction_x = (delta_x > 0) - (delta_x < 0)
    direction_y = (delta_y > 0) - (delta_y < 0)
    projected = list(position)
    # A projected location can cross into a slower range band. Re-evaluate the
    # band a few times so the final lead uses the shell's actual flight time.
    for _ in range(3):
        profile = launcher.launcher_profile(math.dist(observer.pos, projected))
        if profile is None:
            return None
        updated = [
            position[0] + (direction_x * speed * profile["turns"]),
            position[1] + (direction_y * speed * profile["turns"]),
        ]
        if updated == projected:
            break
        projected = updated

    if not (1 <= projected[0] < matchInfo.mapWidth - 1 and 1 <= projected[1] < matchInfo.mapHeight - 1):
        return None
    return projected


def launcherAutoLeadAvailable(matchInfo, target):
    """Require team sight or the highest radar ID before predicting movement."""
    return target is not None and (
        radar.team_has_visual_contact(matchInfo.pov, target)
        or radar.can_aim_at_contact(matchInfo.pov, matchInfo, target)
    )


def printLauncherProfile(mech, launcher, position):
    """Display the launcher band that will govern a shot at ``position``."""
    distance = math.dist(mech.pos, position)
    profile = launcher.launcher_profile(distance)
    if profile is None:
        print(f"Out of range: far profile reaches {launcher.selected_ammo.rangeBands['far'][0]} tiles.")
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
    print(
        details + f"rounds {charges}"
    )
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
        rawOffset = input("Lead offset 'x,y' (positive X east, positive Y north; 'x' to cancel): ").strip().lower()
        if rawOffset == "x":
            return None
        try:
            xOffset, yOffset = (int(value.strip()) for value in rawOffset.split(","))
        except ValueError:
            print("Enter two signed whole numbers separated by one comma.")
            continue

        position = [basePosition[0] + xOffset, basePosition[1] + yOffset]
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
    selection = _read_nonempty("Launch target: ")
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


def squadMenu(matchInfo):
    """Show squad readiness and roster before player-facing squad controls."""
    squad = matchInfo.pov.squad
    entries = [*squad.statusReport().splitlines(), *squad.rosterReport().splitlines()]
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Squad: 'm' switch mech | 's' switch controllable squad | 'x' exit",
        right_panel=("SQUAD", entries),
    )
    choice = input("Squad: ").strip().lower()

    if choice in ("", "x"):
        return
    if choice == "m":
        return selectSquadMech(matchInfo, squad)
    if choice == "s":
        return selectControllableSquad(matchInfo)
    print("Choose 'm', 's', or 'x'.")


def radarMenu(matchInfo):
    """Show every friendly squad's radar contacts nearest to the active mech."""
    observer = matchInfo.pov
    contacts = radar.team_contacts(observer)
    if not contacts:
        print("No enemy radar contacts are currently shared with your team.")
        return

    entries = []
    for index, contact in enumerate(contacts, start=1):
        detail = radar.contact_details(observer, matchInfo, contact)
        entries.append(
            f"'{index}' {detail['classification']} at {detail['position']} "
            f"| {detail['distance']:.1f} tiles"
        )

    pv.printPOV(
        matchInfo, *observer.pos,
        command_text="Radar: enter a listed contact number | 'x' exit",
        right_panel=("TEAM RADAR — NEAREST FIRST", entries),
    )

    selection = input("Select a contact for details, or 'x' to exit: ").strip().lower()
    if selection in ("", "x"):
        return
    if not selection.isdigit() or not 1 <= int(selection) <= len(contacts):
        print("Choose a listed contact number or 'x'.")
        return

    selected_target = contacts[int(selection) - 1]
    observer.focusedEnemy = selected_target
    detail = radar.contact_details(observer, matchInfo, selected_target)
    confirmation = "yes" if detail["visually_confirmed"] else "no"
    detail_entries = [
        f"Classification: {detail['classification']}",
        f"Position: {detail['position']} | Distance: {detail['distance']:.1f} tiles",
        f"Movement: {detail['movement']} | Visually confirmed: {confirmation}",
        f"Radar return: {detail['return_power']} / {detail['threshold']} required",
    ]
    pv.printPOV(
        matchInfo, *detail["position"],
        command_text="Radar contact: 'f' fire at this contact | 'x' exit",
        right_panel=("RADAR CONTACT", detail_entries),
    )
    action = input("Radar contact: 'f' fire at this contact | 'x' exit: ").strip().lower()
    if action == "f":
        return fire(matchInfo, selected_target)
    if action not in ("", "x"):
        print("Choose 'f' or 'x'.")


def optionsMenu(matchInfo):
    """Offer display preferences that do not alter match state."""
    print(
        f"Options: 'w' tactical width ({matchInfo.windowWidth}) | "
        f"'h' tactical height ({matchInfo.windowHeight}) | 'x' exit"
    )
    choice = input("Options: ").strip().lower()
    if choice in ("", "x"):
        return
    if choice not in ("w", "h"):
        print("Choose 'w', 'h', or 'x'.")
        return

    dimension = "width" if choice == "w" else "height"
    minimum = 5 if choice == "w" else pv.MIN_TACTICAL_HEIGHT
    while True:
        size = input(f"Tactical {dimension} (odd whole number, at least {minimum}; 'x' to cancel): ").strip().lower()
        if size == "x":
            return
        if size.isdigit() and int(size) >= minimum and int(size) % 2 == 1:
            if choice == "w":
                matchInfo.windowWidth = int(size)
            else:
                matchInfo.windowHeight = int(size)
            print(f"Tactical {dimension} set to {size}.")
            return
        print(f"Enter an odd whole number of at least {minimum}, or 'x' to cancel.")


def selectSquadMech(matchInfo, squad):
    """Switch the point of view to a mech in the current squad."""
    entries = [
        f"'{index}' {mech.pilot.name} — {mech.mechClass.name} ({round(mech.mechClass.condition)}%)"
        for index, mech in enumerate(squad.mechList, start=1)
    ]
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Mech: enter a listed number | 'x' cancel",
        right_panel=("SWITCH MECH", entries),
    )
    selection = _read_nonempty("Mech: ")
    if selection.lower() == "x":
        return
    if not selection.isdigit() or not 1 <= int(selection) <= len(squad.mechList):
        print("Choose a listed mech number.")
        return
    matchInfo.pov = squad.mechList[int(selection) - 1]
    matchInfo.advTurn = False


def selectControllableSquad(matchInfo):
    """Switch to a non-empty squad explicitly marked as player controlled."""
    squads = [
        squad
        for team in matchInfo.teamList
        for squad in team.squadsList
        if squad.playerControlled and squad.mechList
    ]
    if not squads:
        print("No controllable squads are available.")
        return
    entries = [
        f"'{index}' {squad.name} — {len(squad.mechList)} mechs"
        for index, squad in enumerate(squads, start=1)
    ]
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Squad: enter a listed number | 'x' cancel",
        right_panel=("SWITCH SQUAD", entries),
    )
    selection = _read_nonempty("Squad: ")
    if selection.lower() == "x":
        return
    if not selection.isdigit() or not 1 <= int(selection) <= len(squads):
        print("Choose a listed squad number.")
        return
    matchInfo.pov = squads[int(selection) - 1].mechList[0]
    matchInfo.playerSquad = matchInfo.pov.squad
    matchInfo.advTurn = False


def fireTargetPrompt(matchInfo, defaultTarget=None, weapon=None):
    """Return the direct-fire choices that belong in the tactical command bar."""
    if defaultTarget is None:
        return "Fire target: 'w' weapon | 't' tracked enemy | 'l' last location | 'c' coordinates | 'x' cancel"
    canAim = radar.can_aim_at_contact(matchInfo.pov, matchInfo, defaultTarget)
    prompt = "Press 'Enter' or 'f' to fire."
    if canAim:
        prompt += f" 'a' aim limb ({aimingCostLabel(weapon)}) |"
    return prompt + " 'w' weapon | 't' tracked enemy | 'l' last location | 'c' coordinates | 'x' cancel"


def chooseFireTarget(matchInfo, defaultTarget=None, weapon=None, promptDisplayed=False):
    """Confirm the default target or choose another firing location."""
    mech = matchInfo.pov
    if defaultTarget is not None:
        canAim = radar.can_aim_at_contact(mech, matchInfo, defaultTarget)
        if not promptDisplayed:
            print(fireTargetPrompt(matchInfo, defaultTarget, weapon))
        choice = input("Target: ").strip().lower()
        if choice in ("", "f"):
            return radar.contact_position(mech, defaultTarget), None
        if choice == "a" and canAim:
            aimedLimb = chooseAimedLimb(defaultTarget)
            return None if aimedLimb is None else (radar.contact_position(mech, defaultTarget), aimedLimb)
        if choice == "a":
            print("Limb aiming requires direct visual contact or a fully identified radar return.")
            return None
    else:
        if not promptDisplayed:
            print(fireTargetPrompt(matchInfo, weapon=weapon))
        choice = _read_nonempty("Target: ").lower()

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
    selectedTarget = chooseTrackedContact(matchInfo)
    if selectedTarget is None:
        return None
    # As with launchers, retain the selected contact and reopen the full
    # targeting menu so weapon switching and limb aiming stay available.
    detail = radar.contact_details(mech, matchInfo, selectedTarget)
    pv.printPOV(
        matchInfo, *detail["position"],
        command_text=fireTargetPrompt(matchInfo, selectedTarget, weapon),
    )
    return chooseFireTarget(matchInfo, selectedTarget, weapon, promptDisplayed=True)


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
    selection = _read_nonempty("Tracked target: ")
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

    # Exact target size is required for the size modifier.  Visual contact or
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
        print(f"{index}. {limb.name} — armor {limb.armor}/{limb.startingArmor}, HP {limb.hp}/{limb.startingHP}")
    selection = _read_nonempty("Aim at limb ('x' to cancel): ").lower()
    if selection == "x":
        return None
    if not selection.isdigit() or not 1 <= int(selection) <= len(target.mechClass.limbList):
        print("Choose a listed limb number.")
        return None
    return target.mechClass.limbList[int(selection) - 1]

def gunMenu(matchInfo, target=None): #TODO add ability to exit
    """Select a default weapon, preserving a radar-selected target if present."""

    mech = matchInfo.pov
    gunList = mech.mechClass.gunList

    if len(gunList) == 1:
        gunList[0].defaultGun = True
        print(gunList[0].printShortDesc())
        print("You only have one weapon. It is set as the default for 'f'.")
        return fire(matchInfo, target) if target is not None else None
    elif len(gunList) == 0:
        print("You have no weapons.")
        return


    menuWidth = 0
    for limb in gunList:
        limb.defaultGun = False
        if len(limb.printShortDesc()) > menuWidth:
            menuWidth = len(limb.printShortDesc())
    menuWidth += 4
    
    menuDivider = ""
    i = 1
    while i <= menuWidth:
        i+=1
        menuDivider = f"{menuDivider}-" 

    print("Select the default weapon used by 'f'.")
    for limb in gunList:
        print(menuDivider)
        print(f"'{gunList.index(limb) + 1}' {limb.printShortDesc()}")
    print(menuDivider)

    #get default gun choice from menu
    #TODO add ability to pull a weapon's long description
    playerInput = _read_nonempty("Choose weapon number: ")

    try:
        playerInput = int(playerInput)
        if not 1 <= playerInput <= len(gunList):
            print("Please enter an integer listed in the menu.")
            gunMenu(matchInfo, target)
        else:
            gunList[playerInput - 1].defaultGun = True
            print(f"{gunList[playerInput - 1].name} is now the default for 'f'.")
            return fire(matchInfo, target) if target is not None else None
    except ValueError:
        print("Please enter an integer.")
        gunMenu(matchInfo, target)


def nextMech(matchInfo):
    matchInfo.nextMechinTeam()

def reportMenu(matchInfo):
    """Browse the squad report log inside the right tactical panel."""
    reports = matchInfo.pov.squad.reportLog
    pageSize = max(1, matchInfo.windowHeight - 2)
    page = 1
    pageMax = max(1, (len(reports) + pageSize - 1) // pageSize)
    while True:
        start = (page - 1) * pageSize
        entries = [report[0] for report in reports[start:start + pageSize]] or ["No squad reports."]
        pv.printPOV(
            matchInfo, *matchInfo.pov.pos,
            command_text="Reports: 'n' next | 'p' previous | 'x' exit",
            right_panel=(f"REPORTS {page}/{pageMax}", entries),
        )
        choice = input("Reports: ").strip().lower()
        if choice in ("", "x"):
            return
        if choice == "n" and page < pageMax:
            page += 1
        elif choice == "p" and page > 1:
            page -= 1
        else:
            print("Choose 'n', 'p', or 'x'.")


def unreadReportMenu(matchInfo):
    """Display unread reports in the right panel and mark them as read."""
    unread = [report for report in matchInfo.pov.squad.reportLog if not report[2]]
    for report in unread:
        report[2] = True
    entries = [report[0] for report in unread] or ["No unread reports."]
    pv.printPOV(
        matchInfo, *matchInfo.pov.pos,
        command_text="Unread reports: 'Enter' or 'x' return",
        right_panel=("UNREAD REPORTS", entries),
    )
    input("Unread reports: ")


# Compatibility aliases retain the original callable names while using the
# panel-based report views.
printReportLogPrompt = reportMenu
printReportLog = reportMenu
printUnreads = unreadReportMenu

def helpCommand(matchInfo):
    """Show a concise reference for every command accepted at the main prompt."""
    print("Main commands:")
    print("'q' 'w' 'e' 'a' 's' 'd' 'z' 'c' — move in the matching direction.")
    print("'f' — fire the selected weapon at the nearest tracked contact; menus offer more targeting choices.")
    print("'fire' — choose the default weapon used by 'f'.")
    print("'r' or 'radar' — toggle continuous active radar; it has an energy cost each turn.")
    print("'p' — send a one-turn active-radar pulse.")
    print("'rd' — view shared team radar contacts and fire at one.")
    print("'ab' or 'abilities' — open the active mech's hull abilities.")
    print("'look' or 'l' — inspect the tactical view around map coordinates.")
    print("'st' or 'status' — reopen the default tactical status panel.")
    print("'sq' or 'squad' — show squad readiness, roster, and switching options.")
    print("'rep1' — show unread reports. 'rep' — open the full report log.")
    print("'o' or 'options' — change display options, including tactical width and height.")
    print("'n' or 'next' — switch to another mech in the active squad without ending its turn.")
    print("'end' — hand the squad turn to the next squad.")
    print("'?' — show this command reference.")
    print("Context menus always list their own available keys; use 'x' to cancel where offered.")
    matchInfo.advTurn = False

