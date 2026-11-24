# ASCII Mech Game

An in-progress, terminal-based mech tactics game. It explores land combat where
terrain, visibility, and radar matter as much as raw firepower.

## Run it

Requires Python 3.10 or later.

```text
python -m pip install -r requirements.txt
python main.py
```

Playable maps are a minimum of **40×40** tiles. The start menu offers `'s'` to
launch the demo skirmish and `'o'` for complete display size and map generation.
Choose `'t'` for the **Raid Military Base** test match. It uses a random map
at least 100×100, with an edge-side base and a distant, initially undetected
player deployment. The player controls the skirmish Lancer squad plus a
sensor/two-mortar support squad. Three defending squads each carry two
Bastions and one Kestrel, with terrain knowledge and base-defense orders.

To raid the base, end a squad turn with a mech inside the marked compound
and keep it there until that squad's next turn. Then extract every surviving
player mech using `flee` at a border, or remove all enemy mechs from the map.
Extracting before completing the raid fails the mission. Use `sq` to change
player squads, `m` for map/debug controls, and `quit` to return to the menu.
Test matches also return to the menu after success or failure for rapid retries.

Display width and height describe the whole terminal frame, including the HUD,
tactical map, right-hand information panel, and command panel. The default
111×46 display provides the standard 37×37 tactical map. Under Options, `'p'`
selects a terrain-only map preset and `'m'` exposes individual tile toggles.
Changing an individual toggle marks the map as **Custom**; choosing a preset
again replaces those custom selections. Custom maps use Temperate Frontier
generation frequencies for every enabled tile type. Presets do not change
teams, mech loadouts, spawns, or objectives.

| Preset | Terrain emphasis |
| --- | --- |
| Temperate Frontier | Larger forests, two roads, a two-lane highway with a suburb spur, mountains, and water. |
| Badlands | Heat-hazed desert, mountains, and sparse roads. |
| Mountain Pass | Dense ridges, forest approaches, streams, tunnels, and roads. |
| River Basin | Rivers, lakes, bridges, suburbs, and urban corridors. |
| Super City | Connected 10×10 city blocks covering about half the map. |
| Open Steppe | Long sightlines, scattered rough terrain, roads, and small ponds. |

For a quick manual test, type `end` twice after the map appears. The first
command moves the active turn to the opposing squad; the second begins a new
round and returns it to the player squad.

## Project map

- `main.py` opens the start menu and launches a skirmish.
- `mechgame/runner.py` owns match setup and the command-line loop.
- `mechgame/ui/menu.py` owns the pre-match Skirmish and display-options menus.
- `mechgame/ui/tactical.py` owns terminal rendering for the tactical screen and its panels.
- `mechgame/catalog.py` is the reusable library of named mech, part, and module
  factories, grouped by size class.
- `mechgame/content.py` assembles the playable sensor-Lancer demo scenario.
- `mechgame/world.py` defines terrain and generates maps.
- `mechgame/coordinates.py` owns tactical coordinate validation and direction
  labels. Positions are written `[x, y]`; map storage is indexed `[y][x]`.
- `mechgame/match.py` owns match-wide state and turn calculations.
- `mechgame/terrain.py` defines terrain and map cells.
- `mechgame/radar.py` owns active scans, terrain absorption, radar contacts,
  passive-radar warnings, and radar reports.
- `mechgame/artillery.py` owns delayed launcher impacts, travel timing, and
  landing scatter, including selectable shell payloads.
- `mechgame/effects.py` owns smoke and fire behavior on terrain cells.
- `mechgame/entities.py` defines live mech behavior, movement, and sensing.
- `mechgame/mechs.py` defines mech blueprints, parts, weapons, and modules.
- `mechgame/teams.py` defines squad coordination, reports, and spawning.
- `tests/` contains automated checks for the world-generation boundary.

## Test

```text
python -m unittest discover -s tests
```

Current playable features include procedural maps, spawning, movement, visual
range, shared radar contacts, direct and artillery combat, limb damage,
temporary fire/smoke effects, equipment selection, and a two-team turn cycle.
Enemy AI, campaign flow, saves, and broader automated coverage remain in
development.

The strategic map (`m`) now uses fog of war. Any friendly mech with a
data-sharing helm contributes its visual range to the team's map; explored
terrain remains recorded, while enemies only appear while currently seen.

## Content catalog

Use stable IDs when constructing content. Every catalog call returns a fresh
object, so match damage never leaks into another mech or match.

```python
from mechgame.catalog import create_mech, create_module, create_part

pathfinder = create_mech("lancer.pathfinder")
rifle = create_part(2, "scout_rifle")
holosight = create_module("holosight")
```

`list_catalog()` lists entries grouped under class sizes from flat through
titanic. The current test match fields B's Pathfinder, three standard Lancers,
and Chiki's mortar Lancer against two Bastions and a Kestrel.
