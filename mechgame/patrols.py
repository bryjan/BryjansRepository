"""Turn recorded road footprints into adjacent, repeatable patrol walks."""

import math

_NEIGHBORS = tuple((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)


def recorded_road_walk(match, route, origin=None):
    """Read the surviving roadway in a generated feature, then order it."""
    return connected_walk(
        (point for point in route.tiles if match.map[point[1]][point[0]].terrain.name in {"road", "tunnel"}),
        origin,
    )


def connected_walk(tiles, origin=None):
    """Keep one connected component and order it without jumping road gaps.

    Map stamps record road footprints in row order; highways record separate
    lanes. Neither is necessarily a walking route. Preserve existing ordered
    paths, otherwise walk a spanning tree out and back. This covers the whole
    selected component and naturally repeats without expensive turn-time work.
    """
    ordered = tuple(dict.fromkeys(tiles))
    remaining = set(ordered)
    neighbors = {
        point: sorted((point[0] + dx, point[1] + dy) for dx, dy in _NEIGHBORS
                      if (point[0] + dx, point[1] + dy) in remaining)
        for point in ordered
    }
    components = []
    while remaining:
        start = min(remaining)
        component, pending = {start}, [start]
        remaining.remove(start)
        while pending:
            for point in neighbors[pending.pop()]:
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    pending.append(point)
        if len(component) >= 2:
            components.append(component)
    if not components:
        return ()
    component = min(components, key=lambda points: (
        min(math.dist(origin, point) for point in points) if origin is not None else 0,
        -len(points), min(points),
    ))
    path = tuple(point for point in ordered if point in component)
    if all(b in neighbors[a] for a, b in zip(path, path[1:])):
        return path

    # Iterative DFS avoids recursion limits on large city/highway footprints.
    start = path[0]
    visited, walk = {start}, [start]
    stack = [(start, iter(neighbors[start]))]
    while stack:
        point, adjacent = stack[-1]
        candidate = next(adjacent, None)
        if candidate is None:
            stack.pop()
            if stack:
                walk.append(stack[-1][0])
        elif candidate not in visited:
            visited.add(candidate)
            walk.append(candidate)
            stack.append((candidate, iter(neighbors[candidate])))
    return tuple(walk)
