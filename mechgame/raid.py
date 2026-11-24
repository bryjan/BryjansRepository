"""Raid Military Base debug scenario, deployment and objective lifecycle."""

from dataclasses import dataclass, field
import math

from .ai import SquadGoal
from .stamps import MilitaryBaseStamp
from .world import MapGenerator


@dataclass
class RaidObjective:
    player: object
    defender: object
    base_tiles: frozenset
    held_by: dict = field(default_factory=dict)
    raided: bool = False
    title: str = "Raid Military Base"

    def status(self):
        if self.raided:
            return "Raid complete: extract or clear enemies."
        if self.held_by:
            return "Holding base: survive until this squad's next turn."
        return "Enter the marked base and hold for one turn."

    def end_turn(self, match, squad):
        """Start the one-turn hold when a player ends inside the base."""
        if squad.team is self.player and not self.raided:
            for mech in squad.mechList:
                if tuple(mech.pos) in self.base_tiles:
                    self.held_by[mech] = squad

    def begin_turn(self, match, squad):
        """Surviving in the base through the enemy response completes the raid."""
        if self.raided:
            return
        for mech, owner in list(self.held_by.items()):
            if mech not in match.entities or tuple(mech.pos) not in self.base_tiles:
                self.held_by.pop(mech, None)
            elif owner is squad:
                self.raided = True
                mech.report(match, "Base raid complete! Extract surviving mechs or clear the enemy from the map.", critical=True)
                break

    def moved(self, mech):
        if tuple(mech.pos) not in self.base_tiles:
            self.held_by.pop(mech, None)

    def finish_if_decided(self, match):
        """Extraction requires at least one intact return; elimination alone loses."""
        players = any(s.mechList for s in self.player.squadsList)
        enemies = any(s.mechList for s in self.defender.squadsList)
        extracted = any(mech.team is self.player for mech in match.fledMechs)
        success = self.raided and ((not players and extracted) or not enemies)
        if not success and players:
            return False
        match.matchOver = True
        match.winner = self.player if success else self.defender
        match.resultMessage = f"{self.title}: " + (
            "SUCCESS — base raided and force extracted or enemy cleared."
            if success else "FAILED — raiding force lost or withdrew before completing the raid."
        )
        match.turnEnded = match.advTurn = False
        match.resolvePilotSurvival()
        return True


def setup(match):
    """Place a guaranteed edge base and separated forces on a random map."""
    player, defender = match.teamList
    origin = (match.mapWidth - 16, match.mapHeight // 2 - 4)
    stamp = MilitaryBaseStamp(8, 8)
    footprint = set(stamp.positions(origin))
    match.mapFeatures.military_bases = [base for base in match.mapFeatures.military_bases
                                        if not footprint.intersection(base.tiles)]
    # Scenario content may replace a small footprint of generated terrain.
    # The rest of the map and its random tactical features remain intact.
    for x, y in stamp.positions(origin):
        match.map[y][x].terrain = match.plains
    generator = MapGenerator(match.mapWidth, height=match.mapHeight, rng=match.rng)
    generator.features = match.mapFeatures
    base = generator.add_military_base(match.map, match.road, match.suburb, origin=origin, stamp=stamp)
    if base is None:
        raise ValueError("Could not place the raid base.")
    center = (origin[0] + 4, origin[1] + 4)
    # Clear a compact entry zone so neither player squad starts isolated in
    # a pond or behind an impassable patch, regardless of the chosen preset.
    for y in range(center[1] - 10, center[1] + 11):
        for x in range(1, 10):
            match.map[y][x].terrain = match.plains
    # A narrow access route guarantees that water/mountains cannot seal the
    # player out. It is recorded so road patrol and future route AI can use it.
    access = []
    for x in range(2, origin[0] + 1):
        cell = match.map[center[1]][x]
        cell.terrain = match.road
        access.append(cell)
    match.mapFeatures.add_road("raid_access", access)
    match.mapFeatures.refresh_bridges()
    match.mapFeatures.add_objective("raid_base", "Raid Military Base", "raid_military_base", base.tiles)
    match.mapFeatures.add_tactical_location("raid_base_approach", "Base entrance", "base_entrance", ((origin[0], center[1]),))
    occupied = set()
    for side, team in enumerate((player, defender)):
        for index, squad in enumerate(team.squadsList):
            anchor = (5, center[1] - 6 + index * 10) if side == 0 else (
                center[0], center[1] + (index - 1) * 10,
            )
            positions = [(anchor[0] + dx, anchor[1] + dy)
                         for dx, dy in ((0, 0), (-3, -3), (3, 3), (-3, 3), (3, -3))]
            for mech, position in zip(squad.mechList, positions):
                if position in occupied:
                    raise ValueError("Raid deployment overlaps another unit.")
                occupied.add(position)
                match.map[position[1]][position[0]].terrain = match.plains
                mech.pos = list(position)
                mech.turnStartPos = list(position)
                match.entities.append(mech)
    # Use a conservative open-ground upper bound, including overdrive radar.
    # Terrain only reduces these ranges, so no deployment scan is needed.
    from .radar import entity_detection_threshold
    for guard in defender.squadsList:
        for enemy in guard.mechList:
            for squad in player.squadsList:
                for mech in squad.mechList:
                    distance = math.dist(enemy.pos, mech.pos)
                    radar_range = max(0, (enemy.mechClass.radarPower * 1.4 - entity_detection_threshold(mech.radarSig)) / 2)
                    if distance <= max(enemy.visPower * 1.4, radar_range):
                        raise ValueError("Raid deployment would expose player mechs at the start.")
    defender.mapVisibility.show_all_terrain = True
    defender.mapVisibility.show_all_objectives = True
    player.mapVisibility.show_all_objectives = True
    match.playerSquad = player.squadsList[0]
    match.pov = match.playerSquad.squadLead
    match.raidObjective = RaidObjective(player, defender, frozenset(base.tiles))
    for index, squad in enumerate(defender.squadsList):
        post = (center[0], center[1] + (index - 1) * 10)
        goal = SquadGoal(f"raid_defense_{index}", "raid_defense", "defend_location", 100,
                         (post,), "Defend the military base and its approaches.")
        squad.currentGoal = goal
        squad.currentGoals = [goal]
        squad.goalHistory.append(goal)
        squad.refreshCombatForce()
    for squad in player.squadsList:
        squad.squadLead.report(match,
            f"Raid Military Base at {list(center)}. End a turn inside and stay until that squad's next turn. "
            "Then extract all surviving mechs using 'flee', or clear all enemies. "
            "Use 'sq' to switch squads; 'm' opens the map and debug controls. 'quit' returns to the test menu.",
            critical=True)
