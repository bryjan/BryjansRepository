# ASCII Mech Game — Demo

A terminal-based tactical mech skirmish. Terrain, line of sight, radar,
artillery, damage to individual parts, and squad coordination all matter.

## Start the demo

Requires Python 3.10 or later.

```text
python -m pip install -r requirements.txt
python main.py
```

Choose **Start random skirmish** from the opening menu. Every match generates a
new map and randomized safe spawn positions.

## Demo scenario

Your squad fields a sensor Lancer, three standard Lancers, and a mortar Lancer.
They face two Bastions and a Kestrel. The scenario is designed to try radar
spotting, artillery payloads, direct combat, dash movement, and hull abilities.

## Essential controls

| Input | Action |
| --- | --- |
| `q w e / a d / z x c` | Move in eight directions. |
| `f` | Fire the selected weapon; defaults to the nearest tracked contact. |
| `r` / `p` | Toggle continuous radar / send a one-turn radar pulse. |
| `rd` | Open team radar contacts. |
| `ab` | Use the active mech's hull ability. |
| `sq` | View squad readiness and switch mechs. |
| `rep1` / `rep` | Read new reports / browse the report log. |
| `n` | Switch to another mech in the active squad. |
| `end` | Finish the squad's turn. |
| `?` | Show the complete in-game command reference. |

Context menus list their available keys at the bottom of the tactical screen.
Use `x` to cancel most of them.

## Test

```text
python -m unittest discover -s tests
```

## Project layout

- `main.py` starts the opening menu and demo.
- `mechgame/content.py` assembles the playable scenario.
- `mechgame/catalog.py` provides reusable named mech, part, and module factories.
- `mechgame/runner.py` owns match setup and the interactive match loop.
- `mechgame/radar.py`, `artillery.py`, and `effects.py` own the major tactical systems.
- `tests/` contains automated regression tests.
