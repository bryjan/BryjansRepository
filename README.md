# ASCII Mech Game

An in-progress, terminal-based mech tactics game. It explores land combat where
terrain, visibility, and radar matter as much as raw firepower.

## Run it

Requires Python 3.10 or later.

```text
python -m pip install -r requirements.txt
python main.py
```

The start menu offers `'s'` to launch the demo skirmish and `'o'` to choose
the tactical screen's width and height before play begins.

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
