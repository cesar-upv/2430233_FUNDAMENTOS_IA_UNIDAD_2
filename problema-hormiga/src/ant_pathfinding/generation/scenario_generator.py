"""Random generation of scenarios that are solvable by construction.

Randomness comes from a :class:`random.Random` seeded by the request, never from
the global module, so a given seed always yields the same scenario.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario

_MAX_ATTEMPTS = 100


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """What to generate: grid size, food count, obstacle share and seed."""

    rows: int
    columns: int
    food_count: int
    """The search explores ``cells x 2 ** food_count`` states, so a count above ten is
    impractical on a grid larger than a few hundred cells; keep it in single digits."""
    obstacle_ratio: float
    seed: int | None = None


def generate_scenario(request: GenerationRequest) -> AntScenario:
    """Return a solvable scenario as described by ``request``.

    Raises ``ValueError`` for parameters that cannot describe any scenario, and for
    requests whose obstacles leave no component large enough to host start, goal and
    every food.
    """
    _validate(request)
    rng = random.Random(request.seed)
    cells = [Position(x, y) for y in range(request.rows) for x in range(request.columns)]
    blocked_count = round(len(cells) * request.obstacle_ratio)
    needed = request.food_count + 2
    for _ in range(_MAX_ATTEMPTS):
        blocked = frozenset(rng.sample(cells, blocked_count))
        grid = Grid(width=request.columns, height=request.rows, blocked=blocked)
        anchor = rng.choice(cells)
        if not grid.is_walkable(anchor):
            continue
        component = _walkable_component(grid, anchor)
        if len(component) < needed:
            continue
        start, goal, *foods = rng.sample(sorted(component), needed)
        return AntScenario(grid=grid, start=start, goal=goal, foods=foods)
    raise ValueError(
        f"no component of at least {needed} walkable cells (start + goal + "
        f"{request.food_count} foods) in a {request.rows}x{request.columns} grid with "
        f"obstacle_ratio={request.obstacle_ratio} after {_MAX_ATTEMPTS} attempts: "
        "lower the obstacle ratio, enlarge the grid, or lower the food count"
    )


def _validate(request: GenerationRequest) -> None:
    if request.rows <= 0 or request.columns <= 0:
        raise ValueError(f"rows and columns must be positive, got {request.rows}x{request.columns}")
    if request.food_count < 0:
        raise ValueError(f"food_count must not be negative, got {request.food_count}")
    if not 0.0 <= request.obstacle_ratio <= 1.0:
        raise ValueError(f"obstacle_ratio must be within [0.0, 1.0], got {request.obstacle_ratio}")
    capacity = request.rows * request.columns - 2
    if request.food_count > capacity:
        raise ValueError(
            f"food_count {request.food_count} does not fit: start and goal take two of "
            f"the {request.rows * request.columns} cells of a {request.rows}x{request.columns} grid"
        )


def _walkable_component(grid: Grid, origin: Position) -> frozenset[Position]:
    """Return every walkable cell reachable from the walkable ``origin``."""
    reached = {origin}
    queue = deque([origin])
    while queue:
        for neighbor in grid.neighbors(queue.popleft()):
            if neighbor not in reached and grid.is_walkable(neighbor):
                reached.add(neighbor)
                queue.append(neighbor)
    return frozenset(reached)
