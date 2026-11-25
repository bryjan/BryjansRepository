"""Run with: python -m scripts.benchmark_maps --sizes 100 200 300

Quiet raid scenario timings, not a promise about a large combat simulation.
All output stays in memory; rendering excludes terminal drawing time.
"""

import argparse
from contextlib import redirect_stdout
import gc
import io
import json
import random
from time import perf_counter

from mechgame.runner import Game
from mechgame.ui.tactical import print_overview
from mechgame.ai import execute_squad_combat, execute_squad_movement


def measure(size, seed):
    started = perf_counter()
    match = Game(map_size=size, scenario="raid_military_base", rng=random.Random(seed)).create_match()
    result = {"size": size, "tiles": size * size, "generation_s": round(perf_counter() - started, 3)}
    started = perf_counter()
    match.pov.getVisuals(match)
    result["vision_ms"] = round((perf_counter() - started) * 1000, 1)
    source = next(mech for mech in match.entities if mech.mechClass.radarPower > 0 and mech.team is not match.pov.team)
    source.radarOn = True
    source.sensorBoostMultiplier = 1.4
    started = perf_counter()
    match.refreshRadar()
    result["radar_rebuild_ms"] = round((perf_counter() - started) * 1000, 1)
    with redirect_stdout(io.StringIO()):
        started = perf_counter()
        print_overview(match)
        result["overview_ms"] = round((perf_counter() - started) * 1000, 1)
        started = perf_counter()
        for _ in range(len(match._turn_slots())):
            if not match.pov.squad.playerControlled:
                execute_squad_combat(match)
                execute_squad_movement(match)
            match.nextSquadTurn()
        result["quiet_round_s"] = round(perf_counter() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 200, 300])
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    for size in args.sizes:
        if size < 100:
            parser.error("The raid benchmark uses maps at least 100 tiles wide.")
        gc.collect()
        print(json.dumps(measure(size, args.seed)), flush=True)


if __name__ == "__main__":
    main()
