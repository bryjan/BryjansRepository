# ASCII Mech Game

An in-progress, terminal-based mech tactics game. It explores land combat where
terrain, visibility, and radar matter as much as raw firepower.

## Run it

Requires Python 3.10 or later.

```text
python -m pip install -r requirements.txt
python main.py
```

For a quick manual test, type `end` twice after the map appears. The first
command moves the active turn to the opposing squad; the second begins a new
round and returns it to the player squad.

## Project map

- `main.py` starts the application.
- `mechgame/runner.py` owns match setup and the command-line loop.
- `mechgame/content.py` creates reusable mech definitions and the demo scenario.
- `mechgame/world.py` defines terrain and generates maps.
- `mechgame/match.py` owns match-wide state and turn calculations.
- `mechgame/terrain.py` defines terrain and map cells.
- `mechgame/entities.py`, `mechgame/mechs.py`, and `mechgame/teams.py` are the
  focused import points for units, parts, and group coordination.
- `mechgame/models.py` and `gameClasses.py` preserve the original import paths.
- `mechgame/legacy_models.py` temporarily holds the tightly coupled combat
  implementation while those focused modules are migrated one behavior at a time.
- `tests/` contains automated checks for the world-generation boundary.

## Test

```text
python -m unittest discover -s tests
```

Current playable features include map generation, spawning, movement, visual
range, radar reports, weapon selection, and a two-team turn cycle. Combat, AI,
campaign flow, saves, and a full test suite are still in development.
