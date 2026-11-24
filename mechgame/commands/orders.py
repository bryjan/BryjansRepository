"""Friendly control, basic AI orders and player travel menus."""

from ..coordinates import get_coordinate_input
from ..ui import tactical as pv
from .. import squad_orders


def friendly_squad(match, ai_only=False):
    squads = [s for s in match.pov.team.squadsList if s.playerCommandable and s.mechList
              and (not ai_only or not s.playerControlled)]
    if not squads:
        print("No AI-controlled squads. Use the control submenu to delegate a squad first."
              if ai_only else "No friendly squads available.")
        return None
    pv.printPOV(match, *match.pov.pos,
                command_text="Friendly squads: enter a number | 'x' cancel",
                right_panel=("AI SQUADS" if ai_only else "FRIENDLY SQUADS", [
                    f"'{i}' {s.name} — {'Manual' if s.playerControlled else 'AI'}"
                    for i, s in enumerate(squads, 1)]))
    choice = input("Friendly squad: ").strip().lower()
    return squads[int(choice) - 1] if choice.isdigit() and 1 <= int(choice) <= len(squads) else None


def control_menu(match):
    squad = friendly_squad(match)
    if squad is None:
        return
    pv.printPOV(match, *match.pov.pos,
                command_text="Control: 'a' AI | 'm' manual | 'x' cancel",
                right_panel=("SQUAD CONTROL", [squad.name]))
    choice = input("Control: ").strip().lower()
    if choice in {"a", "m"}:
        try:
            squad_orders.set_control(squad, ai=choice == "a")
        except ValueError as error:
            print(error)


def order_menu(match):
    """Dedicated submenu lists only delegated AI squads before their orders."""
    squad = friendly_squad(match, ai_only=True)
    if squad is None:
        return
    options = {"m": "move", "d": "defend", "p": "patrol", "a": "attack",
               "b": "ambush", "r": "retreat", "f": "flee", "h": "hold", "g": "fire_mission"}
    pv.printPOV(match, *match.pov.pos,
                command_text="Orders: 'm' move | 'd' defend | 'p' road patrol | 'a' attack | 'b' ambush | 'g' Fire Mission | 'r' retreat | 'f' flee | 'h' hold | 'x' cancel",
                right_panel=("AI SQUAD ORDERS", [squad.name, "Choose an order for this AI-controlled squad."]))
    choice = input("Order: ").strip().lower()
    if choice not in options:
        return
    kind = options[choice]
    if kind == "fire_mission":
        return fireMissionMenu(match, squad)
    target, position = None, None
    if kind == "attack":
        from ..coordination import contacts
        enemies = contacts(match, squad.team)
        from ..radar import contact_details
        details = [contact_details(match.pov, match, enemy) for enemy in enemies]
        pv.printPOV(match, *match.pov.pos,
                    command_text="Attack: enter a contact number | 'x' cancel",
                    right_panel=("ATTACK TARGET", [f"'{i}' {d['classification']} at {d['position']}"
                                                for i, d in enumerate(details, 1)]))
        value = input("Target: ").strip()
        if not value.isdigit() or not 1 <= int(value) <= len(enemies):
            return
        target = enemies[int(value) - 1]
    elif kind not in {"hold", "flee"}:
        position = get_coordinate_input(match, f"{kind.capitalize()} location")
        if position == "x":
            return
    try:
        squad_orders.issue(match, squad, kind, position, target)
    except ValueError as error:
        print(error)


def automatic_travel(match):
    squad = match.pov.squad
    squad.autoTravelEnabled = not squad.autoTravelEnabled
    squad.travelWarnings.clear()
    state = "ON" if squad.autoTravelEnabled else "OFF"
    print(f"Automatic following {state}. Move the squad leader; followers use their own AP, MP and energy.")
    if squad.autoTravelEnabled:
        from ..travel import warnings
        warnings(match, squad)


def fireMissionMenu(match, squad):
    """Open the fullest artillery unit's launcher menu without changing turns."""
    from .. import fire_missions, radar
    from .firing import launcherFireMenu
    units = fire_missions.artillery_units(squad)
    if not units:
        print("This squad has no operational artillery with ammunition.")
        return
    original_pov = match.pov
    mech = units[0]
    weapon = max((w for w in mech.mechClass.gunList if w.isLauncher and w.hp > 0), key=fire_missions.ammunition)
    try:
        while True:
            match.pov = mech
            radar.refresh_tracked_enemies(mech)
            try:
                result = launcherFireMenu(match, weapon, fire_mission=fire_missions.queue)
            except ValueError as error:
                print(error)
                return
            if result == "switch_artillery":
                pv.printPOV(match, *mech.pos,
                            command_text="Fire Mission: enter artillery unit number | 'x' cancel",
                            right_panel=("ARTILLERY UNITS", [
                                f"'{index}' {unit.pilot.display_name} — {sum(fire_missions.ammunition(w) for w in unit.mechClass.gunList if w.isLauncher and w.hp > 0)} rounds"
                                for index, unit in enumerate(units, 1)]))
                choice = input("Artillery unit: ").strip()
                if not choice.isdigit() or not 1 <= int(choice) <= len(units):
                    return
                mech = units[int(choice) - 1]
                weapon = max((w for w in mech.mechClass.gunList if w.isLauncher and w.hp > 0), key=fire_missions.ammunition)
            elif result == "switch_launcher":
                weapons = [w for w in mech.mechClass.gunList if w.isLauncher and w.hp > 0]
                pv.printPOV(match, *mech.pos,
                            command_text="Fire Mission: enter launcher number | 'x' cancel",
                            right_panel=("LAUNCHERS", [f"'{index}' {w.name}" for index, w in enumerate(weapons, 1)]))
                choice = input("Launcher: ").strip()
                if not choice.isdigit() or not 1 <= int(choice) <= len(weapons):
                    return
                weapon = weapons[int(choice) - 1]
            else:
                return result
    finally:
        match.pov = original_pov
