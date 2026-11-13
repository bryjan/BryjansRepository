# Next session notes

## Recent changes

- The demo match is a Sensor Lancer and Bastion against two Kestrels.
- Radar supports sustained scans (`r`) and one-turn pulses (`p`), shares radar
  contacts with the squad, and refreshes only when a radar source changes.
- The fire menu defaults to the nearest tracked target. It can change weapon,
  target contacts or coordinates, and aim at a limb for one extra AP.
- Mech (`st`) and squad (`sq`) reports show condition, damaged modules, and
  ammunition. The player can switch among controllable units through `sq`.
- The map frame scales with the tactical window. `o` then `w` changes that
  window during a match. The demo no longer asks for map dimensions at launch.
- Rectangular-map fixes use positions as `[x, y]` and storage as `map[y][x]`.
  Spawning, movement, coordinate input, map drawing, and projectile paths now
  follow that rule.
- Reusable mech, part, and module factories belong in `mechgame/catalog.py`.
  The scenario itself belongs in `mechgame/content.py`.
- Combat implementation is split into `mechgame/entities.py` (live mechs and
  sensing), `mechgame/mechs.py` (blueprints, parts, weapons, and modules), and
  `mechgame/teams.py` (squads and teams).

## Suggested next work

1. Add deterministic tests for rectangular maps: spawning, movement at each
   edge, coordinate targeting, and diagonal projectile paths.
2. Replace older camel-case APIs with snake-case APIs gradually, retaining
   wrappers only until external scripts no longer use them.
3. Decide the next terrain and sensor rules: passive radar, terrain signatures,
   and how radar range should be communicated to players.
4. Add a reproducible demo seed or scenario-selection menu once gameplay is
   stable enough to compare balance changes reliably.

## Important conventions

- Positions are `[x, y]`; access a map cell with `map[y][x]`.
- A larger radar signature is easier to detect. Detection threshold is
  `400 - signature`, with terrain and distance reducing radar power.
- Module stat arrays are ordered `[destroyed, damaged, intact]`.
- Catalog factories must return new objects; combat damage must never change
  the templates used by later matches.
