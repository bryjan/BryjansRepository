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
               "b": "ambush", "r": "retreat", "f": "flee", "h": "hold"}
    pv.printPOV(match, *match.pov.pos,
                command_text="Orders: 'm' move | 'd' defend | 'p' road patrol | 'a' attack | 'b' ambush | 'r' retreat | 'f' flee | 'h' hold | 'x' cancel",
                right_panel=("AI SQUAD ORDERS", [squad.name, "Choose an order for this AI-controlled squad."]))
    choice = input("Order: ").strip().lower()
    if choice not in options:
        return
    kind = options[choice]
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
