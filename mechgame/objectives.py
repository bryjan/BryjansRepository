"""Player-facing mission objectives and snapshot-based squad support requests."""

from dataclasses import dataclass
import math


@dataclass
class SupportRequest:
    kind: str
    sender: object
    position: tuple
    description: str
    round: int
    target: object = None
    dismissed: bool = False

    def status(self, match):
        if self.dismissed:
            return "Dismissed"
        return "Active" if match.matchRound <= self.round + 2 else "Expired"


def request_support(match, sender, recipient, kind, position, description, target=None):
    """Refresh a request rather than duplicating it on each combat pass.

    Position and description are copied at request time. Menus never read a
    hidden target's live location, movement or condition from its reference.
    """
    existing = next((request for request in recipient.supportRequests
                     if request.sender is sender and request.kind == kind and request.target is target), None)
    if existing is None:
        existing = SupportRequest(kind, sender, tuple(position), description, match.matchRound, target)
        recipient.supportRequests.append(existing)
    else:
        existing.position = tuple(position)
        existing.description = description
        existing.round = match.matchRound
        existing.dismissed = False
    return existing


@dataclass
class ObjectiveItem:
    title: str
    status: str
    details: tuple
    request: SupportRequest = None


def items(match, squad):
    """Present main goals first, followed by requests addressed to this squad."""
    result = []
    raid = match.raidObjective
    if raid is not None and squad.team is raid.player:
        xs, ys = zip(*raid.base_tiles)
        center = (round(sum(xs) / len(xs)), round(sum(ys) / len(ys)))
        occupants = raid.occupants(match)
        holding = any(mech in raid.held_since for mech in occupants)
        status = ("Completed" if raid.raided else "Failed" if match.matchOver else
                  "Holding" if holding else "Inside — end turn" if occupants else "In progress")
        distance = min(math.dist(match.pov.pos, point) for point in raid.base_tiles)
        roster = ", ".join(f"{mech.pilot.display_name} at {mech.pos}" for mech in occupants) or "None"
        result.append(ObjectiveItem("Raid Military Base", status, (
            f"Objective marker: yellow 'R' on the map at {list(center)}. Other green 'M' bases do not count.",
            f"Footprint: X {min(xs)}–{max(xs)}, Y {min(ys)}–{max(ys)}.",
            "Zoomed-out map cells cover several tiles; use these bounds to confirm entry.",
            f"Active mech: {'inside objective base' if tuple(match.pov.pos) in raid.base_tiles else 'outside objective base'}; distance {distance:.1f} tiles.",
            f"Friendly mechs inside: {roster}.",
            raid.status(match),
            "End a friendly squad turn with a mech inside the base. Keep it inside and alive through the enemy response until the next friendly round.",
            "Leaving the base interrupts that mech's hold. The first completed hold raids the base for the whole team.",
        )))
        extracted = not any(s.mechList for s in raid.player.squadsList) and any(m.team is raid.player for m in match.fledMechs)
        cleared = not any(s.mechList for s in raid.defender.squadsList)
        result.append(ObjectiveItem("Extract or clear the enemy", "Completed" if extracted or cleared else "Failed" if match.matchOver else "Pending", (
            "After raiding the base, extract all surviving friendly mechs or remove every enemy from the battlefield.",
            "Move onto a border tile and use 'flee' to extract a mech intact.",
            "The battle ends when either team has no active mechs. An unfinished raid is recorded as failed.",
        )))
    else:
        for goal in squad.team.currentGoals:
            result.append(ObjectiveItem(goal.kind.replace("_", " ").title(), "Assigned", (
                goal.message or "Complete the team's assigned objective.",
                f"Locations: {list(goal.locations) or 'No fixed location'}",
                f"Priority: {goal.priority}",
                f"Required roles: {', '.join(goal.required_roles) or 'Any'}",
            )))
    if not result:
        result.append(ObjectiveItem("No main objectives assigned", "—", ("No mission objective has been assigned to this team.",)))
    for request in sorted(squad.supportRequests, key=lambda request: request.round, reverse=True):
        if request.dismissed:
            continue
        distance = math.dist(match.pov.pos, request.position)
        details = [
            f"From: {request.sender.name}", f"To: {squad.name}",
            f"Requested: round {request.round} | Status: {request.status(match)}",
            f"Last reported location: {list(request.position)} | Distance: {distance:.1f} tiles",
            request.description,
            "This is a request-time snapshot; confirm contacts before firing.",
        ]
        if request.kind in {"Artillery", "Smoke"}:
            ammunition = []
            for mech in squad.mechList:
                for weapon in mech.mechClass.gunList:
                    if not weapon.isLauncher:
                        continue
                    for ammo in weapon.ammoTypes:
                        if request.kind == "Smoke" and ammo.payload != "smoke":
                            continue
                        if request.kind == "Artillery" and ammo.payload not in {"explosive", "incendiary"}:
                            continue
                        profile = ammo.profile(math.dist(mech.pos, request.position), weapon.launcher_range_bonus(match, mech))
                        reach = (f"{profile['name']} range, {profile['turns']} round(s) to land, scatter {profile['inaccuracy']}"
                                 if profile else "Out of range")
                        ammunition.append(f"{mech.pilot.display_name}: {ammo.name} — {ammo.charges if ammo.charges is not None else 'Unlimited'} remaining; {reach}; {weapon.apCost} AP/{weapon.energyCost} energy.")
            details.extend(["Available ammunition:", *(ammunition or ["No suitable launcher ammunition in this squad."])])
        result.append(ObjectiveItem(f"{request.kind}: {request.sender.name}", request.status(match), tuple(details), request))
    return result
