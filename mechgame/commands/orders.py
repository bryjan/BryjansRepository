"""Friendly control, basic AI orders and player travel menus."""

from ..coordinates import get_coordinate_input
from ..ui import tactical as pv
from .. import squad_orders


def friendly_squad(match):
    squads = [s for s in match.pov.team.squadsList if s.playerCommandable and s.mechList]
    pv.printPOV(match, *match.pov.pos,
                command_text="Friendly squads: enter a number | 'x' cancel",
                right_panel=("FRIENDLY SQUADS", [
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
        squad_orders.set_control(squad, ai=choice == "a")


def order_menu(match):
    squad = friendly_squad(match)
    if squad is None:
        return
    options = {"m": "move", "d": "defend", "p": "patrol", "a": "attack",
               "b": "ambush", "r": "retreat", "f": "flee", "h": "hold"}
    pv.printPOV(match, *match.pov.pos,
                command_text="Orders: 'm' move | 'd' defend | 'p' road patrol | 'a' attack | 'b' ambush | 'r' retreat | 'f' flee | 'h' hold | 'x' cancel",
                right_panel=("AI ORDERS", [squad.name, "Giving an order enables AI control for this squad."]))
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
        squad_orders.set_control(squad, ai=True)
    except ValueError as error:
        print(error)


def automatic_travel(match):
    squad = match.pov.squad
    if squad.autoTravelTarget is not None:
        squad.autoTravelTarget = None
        print("Automatic travel cancelled.")
        return
    pv.printPOV(match, *match.pov.pos,
                command_text="Auto travel: enter destination x,y | 'x' cancel",
                right_panel=("AUTO TRAVEL", ["Squad follows its leader using normal movement and energy costs.",
                                           "Pauses on contact, danger, blockage or arrival."]))
    position = get_coordinate_input(match, "Travel destination")
    if position == "x":
        return
    if not (0 < position[0] < match.mapWidth - 1 and 0 < position[1] < match.mapHeight - 1):
        print("Choose an interior tile. Use 'flee' for extraction.")
        return
    squad.autoTravelTarget = tuple(position)
    squad.fleeOrdered = False
    squad.ambushLocation = None
    squad.combinedAttack = None
