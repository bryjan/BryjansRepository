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
at least 100×100, with a randomized edge-side base and a distant, initially undetected
player deployment. The player controls the skirmish Lancer squad plus a
sensor/two-mortar support squad. Defenders have terrain knowledge and base-defense
orders: one squad has a Kestrel and two Bastions; another has a Kestrel and a
mortar Lancer; the third has three standard Lancers and a sensor Lancer.
The Kestrel/two-Bastion squad holds visual coverage of the base; the other two
squads start on nearby roads and repeat patrol routes until contact. Assigned
patrols and fixed guards are not silently reassigned to idle ambush positions.
Patrols prefer longer approach roads over compound perimeter loops. Their
stored routes use adjacent connected road cells: gaps split a route, and
stamped perimeter/highway footprints are ordered into walkable out-and-back
paths. Debug logs show the current patrol waypoint as well as SL movement.
Player entry can be on any of the four edges, with varying positions for both
player squads and the base. Terrain generation stays random and seeded runs
remain reproducible. No road is forced from the player spawn to the base;
setup preserves natural approaches and adds only essential water crossings.

To raid the base, end a squad turn with a mech inside the marked compound
and keep it there until that squad's next turn. Then extract every surviving
player mech using `flee` at a border, or remove all enemy mechs from the map.
Extracting before completing the raid fails the mission. Use `sq` to change
player squads, `m` for map/debug controls, and `quit` to return to the menu.
Battles end when a team has no active mechs left, whether destroyed or fled.
The after-action screen shows damage dealt/received, destroyed mechs, pilot
losses and mission objectives, then returns to the menu. Clearing defenders
before completing the base hold ends the battle with that raid objective failed.

The briefed raid base appears as a green `M` on the map through fog without
revealing nearby terrain or enemies. Open `obj` / `objectives`, or choose `'o'`
in the map menu, for main goals and requests addressed to your active squad.
Select an entry for objective rules, progress, coordinates, or support details.
Artillery/smoke requests include distance, suitable ammunition, range, scatter,
flight time and costs. Requests retain their reported positions, expire after
two rounds without renewal, and can be dismissed. Use `'n'` / `'p'` to page.

Open `debug` (or map → `'d'`) for inspection controls. Choose `'o'` for enemy
team/squad orders, goals, patrol/ambush/attack state and unit resources; choose
`'l'` for enemy AI decisions, order history and reports. These paginated views
intentionally expose debug information without changing fog, enemy report read
flags or the AI's own knowledge. Each squad retains its last 200 decision entries.

## Map size and profiling

Run `python -m scripts.benchmark_maps --sizes 100 200 300` for a repeatable
quiet-raid benchmark. It measures generation, vision, a radar rebuild, overview
rendering to memory, and one round of updates/AI with the normal 17-mech roster.

Example local measurements (seed 7; hardware and terrain affect results):

| Map | Tiles | Generation | Quiet round | Radar rebuild |
| --- | ---: | ---: | ---: | ---: |
| 100×100 | 10,000 | 1.1 s | 0.30 s | 48 ms |
| 200×200 | 40,000 | 8.2 s | 1.01 s | 195 ms |
| 300×300 | 90,000 | 35.0 s | 1.87 s | 405 ms |

200×200 is a reasonable next test size; 300×300 is usable but has noticeable
startup/turn delays in the current implementation. Larger populations, multiple
active radars, combat and terrain effects add work. There is no fixed upper map
limit, but maps above this tested range need profiling rather than a performance
guarantee. Generation spends most of its time scanning candidate placements for
military bases and city blocks; runtime still has several whole-map visibility,
radar-clear and effect scans. Those are the main targets before much larger maps.

In the squad menu (`sq`), use `'a'` to switch any friendly squad between AI and
manual control. Use `'o'` to give move, defend, road patrol, attack, ambush,
retreat, flee or hold orders from the dedicated AI Orders submenu, which lists
only AI-controlled squads. Player orders are retained rather than replaced by
the team's automatic planner. At least one surviving squad must remain manual;
if that squad is destroyed, ejected or extracted, a surviving friendly squad
automatically returns to manual control.

For a **Fire Mission**, open `sq` → `'o'` AI Orders, select a squad, then `'g'`.
Its artillery mech carrying the most ammunition opens in the launcher fire
menu. Use `'u'` to switch artillery units and `'w'` to switch launchers; ammo,
coordinates, tracked targets and lead controls work as usual. Confirming plots
one shot for that mech's next AI squad turn, with no out-of-turn AP or ammo cost.
The menu stays open after each confirmed shot: choose more payloads/locations,
or repeat the last location with Enter/`f`, then press `'x'` to finish. Each
plotted round is retained; the queue checks remaining ammunition and the mech's
AP/energy capacity. Direct-fire and ordinary launcher menus also stay open
until cancelled, spending actual resources for each confirmed shot.
All player-owned squads,
including delegated AI squads, act before enemy squads each round.
Launcher flight times count match rounds, not individual squad handoffs: a
three-round shell fired in round 0 lands in round 3 regardless of squad count.
Zero-round ammunition still lands immediately. The launch message names the
scheduled impact round.

AI squads hit by an unknown source briefly prioritize repositioning over firing,
staging and ordinary formation holds, using available movement down to the
double-time reserve floor. Manual squads receive a critical warning instead of
being moved automatically. Audible weapons give an eight-way direction and an
estimated search waypoint, never a hidden shooter's exact coordinates. Scouts,
sensors and skirmishers investigate the least-recently observed nearby areas;
revealed terrain is separate from actual visual-observation timestamps.
During an active search, available AI artillery can fire scouting payloads to
reveal stale areas, with a team cooldown and duplicate-area suppression. These
payloads reveal nothing until they land normally. Explicit player orders and
retreat/stealth discipline retain priority outside immediate evasive movement.

Use `auto` (or `'v'` in the squad menu) to toggle automatic following. Move the
squad leader manually; after each move the other mechs use normal formation
rules, AP, MP and energy reserves to follow. When the leader is on a road or
tunnel, followers join that road and use road-following without minimum spacing.
Warnings appear when any mech drops below 50% energy or a follower lags beyond
the leader's fixed 10-tile formation range. Each mech also stays within five
tiles of its nearest teammate, retaining three-tile minimum spacing off-road.
Followers already in formation can hold position;
road columns advance front to back and retry after a teammate clears a cell.
You still choose when
to end the turn. Toggle `auto` again to disable following. `quit` abandons the
match without saving it or producing an after-action result.

Movement also accepts numpad digits with Num Lock on: `7 8 9` for up-left,
up, up-right; `4 6` for left/right; `1 2 3` for down-left, down, down-right.
Use `5` or `wait` to stay in place for one AP without spending MP or energy.
Automatic followers also move when the leader waits and before `end`, so a
stationary or exhausted leader can let lagging mechs catch up. Waiting does
not regenerate energy or advance artillery/effect timers; those use normal rounds.

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
