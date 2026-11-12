# ASCII Mech Game

An in-progress, terminal-based mech tactics game. It explores land combat where
terrain, visibility, and radar matter as much as raw firepower.

## Run it

Requires Python 3.10 or later.

```text
python -m pip install -r requirements.txt
python main.py
```

## Project map

- `main.py` starts the application.
- `mechgame/runner.py` owns match setup and the command-line loop.
- `mechgame/content.py` creates reusable mech definitions and the demo scenario.
- `mechgame/world.py` defines terrain and generates maps.
- `mechgame/models.py` contains the combat and entity domain model.
- `gameClasses.py` keeps the original import path working for existing add-ons.
- `tests/` contains automated checks for the world-generation boundary.

## Test

```text
python -m unittest discover -s tests
```

Current playable features include map generation, spawning, movement, visual
range, radar reports, and weapon selection. Combat, AI, campaign flow, saves,
and a full test suite are still in development.
