"""Terminal rendering for tactical gameplay and contextual panels."""

import termcolor
import textwrap
from mechgame.mechs import MAX_HULL_ART_HEIGHT
from mechgame import radar

SIDE_PANEL_WIDTH = 34
COMMAND_PANEL_ROWS = 3
# The outer map frame uses two columns per terrain tile and reserves the right
# panel plus its three separating border columns.
DISPLAY_WIDTH_OVERHEAD = SIDE_PANEL_WIDTH + 3
# One outer border, two HUD rows, two shared dividers, a three-row command
# panel, and its closing border sit outside the tactical map rows.
DISPLAY_HEIGHT_OVERHEAD = 9
MIN_TACTICAL_WIDTH = 21
# A damaged mortar Lancer is the tallest current detail set. Reserve space
# for its cockpit warning and the largest allowed hull art, then round up to
# an odd dimension so the tactical camera can stay centered.
MAX_STATUS_DETAIL_ROWS = 13
_minimum_side_panel_rows = MAX_HULL_ART_HEIGHT + 2 + MAX_STATUS_DETAIL_ROWS
MIN_TACTICAL_HEIGHT = (
    _minimum_side_panel_rows
    if _minimum_side_panel_rows % 2 else _minimum_side_panel_rows + 1
)
# The normal game view is deliberately much larger than the minimum needed by
# the information panels. Players can still choose any supported odd size.
DEFAULT_TACTICAL_SIZE = 37
DEFAULT_DISPLAY_WIDTH = (DEFAULT_TACTICAL_SIZE * 2) + DISPLAY_WIDTH_OVERHEAD
DEFAULT_DISPLAY_HEIGHT = DEFAULT_TACTICAL_SIZE + DISPLAY_HEIGHT_OVERHEAD
MIN_DISPLAY_WIDTH = (MIN_TACTICAL_WIDTH * 2) + DISPLAY_WIDTH_OVERHEAD
MIN_DISPLAY_HEIGHT = MIN_TACTICAL_HEIGHT + DISPLAY_HEIGHT_OVERHEAD


def tactical_dimensions(display_width, display_height):
    """Convert an exact terminal frame size into its centered map viewport.

    Terrain cells occupy two columns, so a centered odd-width map requires a
    display width that is three more than a multiple of four.  A centered
    odd-height map similarly requires an even full display height.
    """
    if display_width < MIN_DISPLAY_WIDTH or display_width % 4 != 3:
        raise ValueError(
            f"Display width must be at least {MIN_DISPLAY_WIDTH} and equal to 3 modulo 4."
        )
    if display_height < MIN_DISPLAY_HEIGHT or display_height % 2:
        raise ValueError(
            f"Display height must be an even number of at least {MIN_DISPLAY_HEIGHT}."
        )
    return (
        (display_width - DISPLAY_WIDTH_OVERHEAD) // 2,
        display_height - DISPLAY_HEIGHT_OVERHEAD,
    )


def display_dimensions(tactical_width, tactical_height):
    """Return the complete terminal frame needed by a tactical viewport."""
    return (
        (tactical_width * 2) + DISPLAY_WIDTH_OVERHEAD,
        tactical_height + DISPLAY_HEIGHT_OVERHEAD,
    )


def _print_panel_text(text, width):
    """Print wrapped panel text without exceeding the tactical-map width."""
    for line in textwrap.wrap(text, width=width) or [""]:
        print(f"|{line:<{width}}|")


def _print_tactical_footer(width):
    """Print the command row in a standalone frame for menu-only callers."""
    divider = "+" + ("-" * width) + "+"
    print(divider)
    _print_panel_text("'f' Fire | 'r' Toggle Radar | 'rd' Contacts | 'ab' Abilities | 'sq' Squad | 'o' Options | 'n' Next | '?' Help | 'end' End Turn", width)
    print(divider)


def _condition_color(condition):
    """Choose an immediately readable color for a mech's average condition."""
    if condition <= 34:
        return "red"
    if condition <= 66:
        return "yellow"
    return "green"


def _centered_art_lines(mech_art, width, color):
    """Return one centered hull silhouette without exposing extra statistics."""
    lines = []
    for art_line in mech_art:
        left_padding = (width - len(art_line)) // 2
        right_padding = width - len(art_line) - left_padding
        lines.append(
            f"|{' ' * left_padding}{termcolor.colored(art_line, color)}{' ' * right_padding}|"
        )
    return lines


def _centered_mech_lines(mech, width):
    """Return the active mech's hull art, colored by average condition."""
    return _centered_art_lines(
        mech.mechClass.hull.asciiArt,
        width,
        _condition_color(mech.mechClass.condition),
    )


def _weapon_status(weapon):
    """Describe one weapon and its usable ammunition for the side panel."""
    if weapon.isLauncher:
        ammunition = ", ".join(
            f"{ammo.name} {ammo.charges}/{ammo.maxCharges}"
            if ammo.charges is not None else f"{ammo.name} Unlimited"
            for ammo in weapon.ammoTypes
        )
    else:
        ammunition = (
            "Unlimited" if weapon.charges is None
            else f"{weapon.charges}/{weapon.maxCharges}"
        )
    return f"{weapon.name}: {ammunition}"


def _panel_text_lines(text, width):
    """Wrap one status entry into already-bordered side-panel rows."""
    return [f"|{line:<{width}}|" for line in textwrap.wrap(text, width=width) or [""]]


def _finish_panel_lines(lines, height, width):
    """Clip low-priority rows and pad the panel to match the map height."""
    lines = lines[:height]
    return lines + [f"|{'':<{width}}|" for _ in range(height - len(lines))]


def _add_critical_warning(matchInfo, lines, height, width):
    """Reserve the final default-panel row for unread critical reports."""
    if not any(critical and not read for _, critical, read in matchInfo.pov.squad.reportLog):
        return lines
    warning = "Critical reports!"
    left_padding = (width - len(warning)) // 2
    right_padding = width - len(warning) - left_padding
    lines[-1] = (
        f"|{' ' * left_padding}{termcolor.colored(warning, 'yellow')}"
        f"{' ' * right_padding}|"
    )
    return lines


def menu_panel_lines(title, entries, height, width=SIDE_PANEL_WIDTH):
    """Build a temporary right-panel menu with a title and wrapped entries."""
    lines = [
        f"|{title[:width]:^{width}}|",
        "+" + ("-" * width) + "+",
    ]
    for entry in entries:
        lines.extend(_panel_text_lines(entry, width))
    return _finish_panel_lines(lines, height, width)


def _own_mech_panel_lines(mech, height, width):
    """Build the status/weapon fallback when the team tracks no enemies."""
    abilities = ", ".join(
        f"{ability.name} {'Unlimited' if ability.maxCharges is None else f'{ability.charges}/{ability.maxCharges}'}"
        for ability in mech.mechClass.hull.abilities
    ) or "None"
    weakest_limb = min(mech.mechClass.limbList, key=lambda limb: limb.limbCon)
    weakest_condition = round(weakest_limb.limbCon * 100)
    entries = [
        f"Condition: {round(mech.mechClass.condition)}%",
        f"Most damaged: {weakest_limb.name} ({weakest_condition}%)",
    ]
    if mech.cockpit.status < 2:
        pilot_condition = "Injured" if mech.cockpit.status == 1 else "Lost"
        entries.append(f"Pilot: {pilot_condition} (cockpit damaged)")
    entries.extend([
        f"AP: {mech.ap}/{mech.mechClass.apMax} | MP: {mech.mp}/{mech.mechClass.mpMax}",
        f"Energy: {mech.energy}/{mech.mechClass.energyMax} | Regen: {mech.mechClass.energyGen}",
        "Weapons:",
        *(_weapon_status(weapon) for weapon in mech.mechClass.gunList),
        f"Abilities: {abilities}",
        f"Radar: {'ON' if mech.radarOn else 'OFF'} | Speed: {mech.speed}",
    ])
    # The upper block stays visually stable: silhouette, centered identity,
    # then a right-panel-only divider before live details.
    identity = f"{mech.pilot.name} - {mech.mechClass.name}"[:width]
    lines = [
        *_centered_mech_lines(mech, width),
        f"|{identity:^{width}}|",
        "+" + ("-" * width) + "+",
    ]
    for entry in entries:
        lines.extend(_panel_text_lines(entry, width))
    return _finish_panel_lines(lines, height, width)


def _focused_contact_panel_lines(matchInfo, contacts, focus, height, width):
    """Build a sensor-limited target view plus a compact contact list."""
    observer = matchInfo.pov
    detail = radar.contact_details(observer, matchInfo, focus)
    identity = f"FOCUS: {detail['classification']}"[:width]
    lines = []
    # Hull art is only safe to show once visual confirmation or radar level 3
    # identifies the chassis. It is deliberately white: condition is unknown.
    if detail["silhouette_known"]:
        lines.extend(_centered_art_lines(focus.mechClass.hull.asciiArt, width, "white"))
    lines.extend([
        f"|{identity:^{width}}|",
        "+" + ("-" * width) + "+",
    ])
    sensor_source = "Visual" if detail["visually_confirmed"] else f"Radar ID {detail['radar_level']}"
    entries = [
        f"Position: {detail['position']} | Distance: {detail['distance']:.1f}",
        f"Movement: {detail['movement']}",
        f"Sensors: {sensor_source}",
        f"Return: {detail['return_power']} / {detail['threshold']}",
        "Tracked contacts:",
    ]
    for contact in contacts:
        contact_detail = radar.contact_details(observer, matchInfo, contact)
        marker = ">" if contact is focus else "-"
        entries.append(
            f"{marker} {contact_detail['classification']} {contact_detail['position']} "
            f"({contact_detail['distance']:.1f})"
        )
    for entry in entries:
        lines.extend(_panel_text_lines(entry, width))
    return _finish_panel_lines(lines, height, width)


def _side_panel_lines(matchInfo, height, width=SIDE_PANEL_WIDTH):
    """Show contact intelligence first, falling back to own weapon readiness."""
    observer = matchInfo.pov
    contacts = radar.tracked_contacts(observer)
    focus = radar.panel_focus(observer)
    if focus is not None:
        lines = _focused_contact_panel_lines(matchInfo, contacts, focus, height, width)
    else:
        lines = _own_mech_panel_lines(observer, height, width)
    return _add_critical_warning(matchInfo, lines, height, width)


def _hud_lines(matchInfo, width):
    """Build the stable, full-width resource HUD shown above the tactical view."""
    mech = matchInfo.pov
    condition = round(mech.mechClass.condition)
    terrain = matchInfo.map[mech.pos[1]][mech.pos[0]].terrain.name
    entries = [
        f"HUD | {mech.pilot.name} | Pos: {mech.pos} | {condition}% | Tile: {terrain}",
        (
            f"AP {mech.ap}/{mech.mechClass.apMax} | MP {mech.mp}/{mech.mechClass.mpMax} | "
            f"EN {mech.energy}/{mech.mechClass.energyMax} +{mech.mechClass.energyGen} | "
            f"SPD {mech.speed} | RADAR {'ON' if mech.radarOn else 'OFF'}"
        ),
    ]
    lines = []
    for entry in entries:
        # A wrapped command separator can otherwise begin the next row with
        # ``|`` and look like a second left-hand border.
        lines.extend(line.lstrip("| ") for line in textwrap.wrap(entry, width=width) or [""])
    return lines


def _command_lines(width, command_text=None):
    """Build either the normal commands or the active menu's available keys."""
    if command_text is None:
        command_text = (
            "Commands | 'f' Fire | 'r' Toggle Radar | 'rd' Contacts | 'ab' Abilities | 'sq' Squad | "
            "'o' Options | 'n' Next | '?' Help | 'end' End Turn"
        )
    # Separators may land at a wrap boundary; trimming both edges prevents a
    # separator from visually merging with the panel's actual border.
    return [line.strip("| ") for line in textwrap.wrap(command_text, width=width)]


def _command_panel_lines(width, command_text=None):
    """Keep the bottom panel at its reserved height for a stable display."""
    lines = _command_lines(width, command_text)
    return lines + [""] * max(0, COMMAND_PANEL_ROWS - len(lines))


# A continuous road or tunnel is the strategic representation of a route. It
# needs to remain visible even across a broad river or lake, while water still
# receives a smaller link bonus to preserve unbridged river crossings.
OVERVIEW_ROUTE_BONUSES = {"road": 100, "tunnel": 100, "water": 24}
OVERVIEW_ROUTE_TERRAINS = set(OVERVIEW_ROUTE_BONUSES)


def _route_crosses_chunk(chunk, terrain):
    """Return whether connected route tiles reach at least two chunk edges."""
    height, width = len(chunk), len(chunk[0])
    positions = {
        (row_index, column_index)
        for row_index, row in enumerate(chunk)
        for column_index, cell in enumerate(row)
        if cell.terrain is terrain
    }
    while positions:
        frontier = [positions.pop()]
        edges = set()
        while frontier:
            row, column = frontier.pop()
            if row == 0:
                edges.add("south")
            if row == height - 1:
                edges.add("north")
            if column == 0:
                edges.add("west")
            if column == width - 1:
                edges.add("east")
            for delta_row, delta_column in (
                (-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1),
                (1, -1), (1, 0), (1, 1),
            ):
                neighbor = (row + delta_row, column + delta_column)
                if neighbor in positions:
                    positions.remove(neighbor)
                    frontier.append(neighbor)
        if len(edges) >= 2:
            return True
    return False


def overview_terrain(chunk):
    """Choose a chunk symbol through weighted terrain voting and route links."""
    terrain_counts = {}
    for row in chunk:
        for cell in row:
            terrain_counts[cell.terrain] = terrain_counts.get(cell.terrain, 0) + 1

    scored_terrain = []
    for terrain, count in terrain_counts.items():
        score = count * terrain.overviewWeight
        if terrain.name in OVERVIEW_ROUTE_TERRAINS and _route_crosses_chunk(chunk, terrain):
            score += OVERVIEW_ROUTE_BONUSES[terrain.name]
        scored_terrain.append((score, count, terrain.overviewWeight, terrain))
    # The stable terrain name tie-break keeps seeded map rendering reproducible.
    return max(scored_terrain, key=lambda item: (item[0], item[1], item[2], item[3].name))[3]


def _overview_chunks(matchInfo, width, height):
    """Partition the full map into complete rectangular overview chunks."""
    rows = []
    for display_y in range(height):
        start_y = (display_y * matchInfo.mapHeight) // height
        end_y = ((display_y + 1) * matchInfo.mapHeight) // height
        row = []
        for display_x in range(width):
            start_x = (display_x * matchInfo.mapWidth) // width
            end_x = ((display_x + 1) * matchInfo.mapWidth) // width
            row.append([
                map_row[start_x:end_x]
                for map_row in matchInfo.map[start_y:end_y]
            ])
        rows.append(row)
    return rows


def _display_overview_chunk(matchInfo, chunk):
    """Render the selected terrain, or a debug-visible entity/effect on top."""
    entities = [
        entity
        for entity in matchInfo.entities
        if any(entity.pos == cell.pos for row in chunk for cell in row)
    ]
    active = next((entity for entity in entities if entity is matchInfo.pov), None)
    if active is not None:
        active.displayObject(active=True)
        return
    if len(entities) == 1:
        entities[0].displayObject()
        return
    if len(entities) > 1:
        print(termcolor.colored("+", "yellow"), end=" ")
        return
    effects = [effect for row in chunk for cell in row for effect in cell.effects]
    if effects:
        effect = next((effect for effect in effects if effect.name == "fire"), effects[0])
        print(termcolor.colored(effect.symbol, effect.color), end=" ")
        return
    overview_terrain(chunk).displayTerrain()


def print_overview(matchInfo):
    """Render a full-map debug overview inside the normal tactical frame.

    TODO(fog-of-war): use the viewing team's ``mapVisibility`` policy and its
    persistent discovery records to limit each chunk.  For now the overview is
    intentionally debug-visible: all terrain, effects, and entities are shown.
    """
    window_width = min(matchInfo.windowWidth, matchInfo.mapWidth)
    window_height = min(matchInfo.windowHeight, matchInfo.mapHeight)
    chunks = _overview_chunks(matchInfo, window_width, window_height)
    panel_width = window_width * 2
    top_divider = "+" + ("-" * panel_width) + "+" + ("-" * SIDE_PANEL_WIDTH) + "+"
    full_panel_width = panel_width + SIDE_PANEL_WIDTH + 1
    full_divider = "+" + ("-" * full_panel_width) + "+"
    side_lines = _side_panel_lines(matchInfo, window_height)

    print(full_divider)
    for line in _hud_lines(matchInfo, full_panel_width):
        print(f"|{line:<{full_panel_width}}|")
    print(top_divider)
    for row, side_line in zip(reversed(chunks), side_lines):
        print("|", end="")
        for chunk in row:
            _display_overview_chunk(matchInfo, chunk)
        print(side_line)
    print(full_divider)
    for line in _command_panel_lines(full_panel_width, "Map overview: 'Enter' or 'x' return"):
        print(f"|{line:<{full_panel_width}}|")
    print(full_divider)


def printPOV(matchInfo, povX, povY, command_text=None, right_panel=None):
    """Render a rectangular tactical window centered on the supplied map position."""
    from mechgame.terrain import Cell

    # Small maps should not look empty merely because one requested dimension
    # exceeds the generated world. Each dimension stays odd so the point of
    # view remains centered independently on both axes.
    windowWidth = min(matchInfo.windowWidth, matchInfo.mapWidth)
    windowHeight = min(matchInfo.windowHeight, matchInfo.mapHeight)
    if windowWidth % 2 == 0:
        windowWidth -= 1
    if windowHeight % 2 == 0:
        windowHeight -= 1
    widthExtend = (windowWidth - 1) // 2
    heightExtend = (windowHeight - 1) // 2

    # Make the rectangular cell window.
    mapWindow = []
    xRow = []
    y = povY - heightExtend
    while y <= povY + heightExtend:
        x = povX - widthExtend
        while x <= povX + widthExtend:
            if y < 0 or y >= matchInfo.mapHeight or x < 0 or x >= matchInfo.mapWidth:
                # Mark space beyond the generated world as a border rather
                # than blank terrain, making map limits immediately obvious.
                xRow.append(Cell(matchInfo.border,[x, y]))
            else:
                xRow.append(matchInfo.map[y][x])
            x += 1
        # Tactical coordinates use a Cartesian convention: larger Y values are
        # farther north and therefore appear higher on the displayed map.
        mapWindow.insert(0, xRow)
        y += 1
        xRow = []

    
    # Each map cell renders as a symbol plus one trailing space, so the frame
    # width scales with the configured horizontal view dimension.
    panelWidth = windowWidth * 2
    topDivider = "+" + ("-" * panelWidth) + "+" + ("-" * SIDE_PANEL_WIDTH) + "+"
    fullPanelWidth = panelWidth + SIDE_PANEL_WIDTH + 1
    fullDivider = "+" + ("-" * fullPanelWidth) + "+"
    sideLines = (
        menu_panel_lines(right_panel[0], right_panel[1], windowHeight)
        if right_panel is not None else _side_panel_lines(matchInfo, windowHeight)
    )
    # The HUD remains in one dependable place above the map, independent of
    # how much detail the active mech panel can fit at this window height.
    print(fullDivider)
    for line in _hud_lines(matchInfo, fullPanelWidth):
        print(f"|{line:<{fullPanelWidth}}|")
    # This segmented edge simultaneously closes the HUD and opens the map and
    # active-mech panels, keeping the entire console in one shared frame.
    print(topDivider)
    for row, sideLine in zip(mapWindow, sideLines):
        print("|", end="")
        for cell in row:
            if cell.terrain == matchInfo.border:
                cell.terrain.displayTerrain() #display borders
            elif cell.canSee == True:
                    cell.displayCell(matchInfo) #already anticipates entities on cell, will display entity if visible
            elif cell.radarReturn == True:
                    cell.displayRadarReturn(matchInfo)
            else:
                 print(" ", end = " ")
        print(sideLine)
    # This shared divider closes both upper panels and opens the command bar.
    print(fullDivider)
    for line in _command_panel_lines(fullPanelWidth, command_text):
        print(f"|{line:<{fullPanelWidth}}|")
    print(fullDivider)
    return
    
