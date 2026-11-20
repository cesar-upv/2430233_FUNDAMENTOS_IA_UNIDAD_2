"""References written independently of the code under test.

Nothing here imports from ``ant_pathfinding``, except the one explicit bridge
:func:`to_scenario`, which exists only to hand a raw scenario to the engine. The grids, the
states and the queues are the ones written in this file, so an error in the search engine
cannot cancel out an error in a reference.

Four references live here, deliberately different in shape from the implementation:

* :func:`held_karp` - the optimum found by minimising over *every* order in which the food
  could be visited, costed with cell-to-cell distances alone. It never builds a state space,
  so it shares nothing with a search over ``(position, collected)`` states.
* :func:`ucs_mask` - uniform-cost search with the collected food packed into an integer bitmask,
  so its state is a plain ``(mask, cell)`` tuple.
* :func:`fifo_bfs` - a hand-written deque loop over ``(cell, collected)`` tuples, reporting its
  pop count, used to check that the engine's BFS is pop-for-pop a FIFO loop.
* :func:`true_remaining` - the exact cost of the sub-problem that starts from one state,
  ``None`` when that state admits no completion.

A scenario is a plain mapping of tuples rather than an ``AntScenario``.
"""

from __future__ import annotations

import itertools
from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from ant_pathfinding.domain.scenario import AntScenario

Cell = tuple[int, int]
State = tuple[Cell, frozenset[Cell]]

__all__ = [
    "FifoResult",
    "OracleGrid",
    "OracleScenario",
    "bfs_dist",
    "fifo_bfs",
    "held_karp",
    "make",
    "reachable_states",
    "to_scenario",
    "true_remaining",
    "ucs_mask",
]


class OracleGrid:
    """A walkable-cell oracle with no relation to the production ``Grid``."""

    __slots__ = ("height", "walls", "width")

    def __init__(self, width: int, height: int, walls: frozenset[Cell]) -> None:
        self.width = width
        self.height = height
        self.walls = set(walls)

    def walkable(self, cell: Cell) -> bool:
        """Whether the cell is inside the bounds and not a wall."""
        x, y = cell
        inside = 0 <= x < self.width and 0 <= y < self.height
        return inside and cell not in self.walls

    def neighbours(self, cell: Cell) -> list[Cell]:
        """Walkable orthogonal neighbours in the drawing order: east, south, west, north.

        The order is load-bearing, not cosmetic. It is the same order ``Position.neighbors``
        uses, and it is what makes a FIFO reference loop pop states in the same order as the
        engine: a reference written east, west, south, north disagrees with the engine on the
        parent map, and therefore on the path and on ``expanded_states``, while still finding
        an equally optimal one.
        """
        x, y = cell
        candidates = ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1))
        return [candidate for candidate in candidates if self.walkable(candidate)]


class OracleScenario(TypedDict):
    """One problem instance as plain data."""

    grid: OracleGrid
    start: Cell
    goal: Cell
    foods: frozenset[Cell]


def make(
    width: int,
    height: int,
    walls: frozenset[Cell],
    start: Cell,
    goal: Cell,
    foods: frozenset[Cell] = frozenset(),
) -> OracleScenario:
    """Return an oracle scenario of raw tuples."""
    return OracleScenario(
        grid=OracleGrid(width, height, walls), start=start, goal=goal, foods=foods
    )


def to_scenario(oracle_scenario: OracleScenario) -> AntScenario:
    """Cross over to the production ``AntScenario`` so the engine can be run on it.

    The one place this module touches the package, and only to hand a raw scenario over.
    """
    from ant_pathfinding.domain.grid import Grid
    from ant_pathfinding.domain.position import Position
    from ant_pathfinding.domain.scenario import AntScenario

    return AntScenario(
        grid=Grid(
            width=oracle_scenario["grid"].width,
            height=oracle_scenario["grid"].height,
            blocked=frozenset(Position(*cell) for cell in oracle_scenario["grid"].walls),
        ),
        start=Position(*oracle_scenario["start"]),
        goal=Position(*oracle_scenario["goal"]),
        foods=frozenset(Position(*cell) for cell in oracle_scenario["foods"]),
    )


def bfs_dist(grid: OracleGrid, origin: Cell, target: Cell) -> int | None:
    """Cell-to-cell distance, or ``None`` when the target cannot be walked to."""
    if origin == target:
        return 0
    seen = {origin: 0}
    queue = deque([origin])
    while queue:
        cell = queue.popleft()
        for neighbour in grid.neighbours(cell):
            if neighbour in seen:
                continue
            if neighbour == target:
                return seen[cell] + 1
            seen[neighbour] = seen[cell] + 1
            queue.append(neighbour)
    return None


def held_karp(oracle_scenario: OracleScenario) -> tuple[bool, int | None]:
    """The optimum as "cheapest complete tour", found without any search over states.

    Every order in which the food could be visited is enumerated and each order is costed with
    the pairwise distances between the start, the foods and the goal. Walking through the same
    cell twice in two different orders is invisible here, which is precisely why this
    reference is independent of the engine's state space.
    """
    grid = oracle_scenario["grid"]
    foods = sorted(oracle_scenario["foods"])
    nodes: list[Cell] = [oracle_scenario["start"], *foods, oracle_scenario["goal"]]
    count = len(nodes)
    pairwise = [[bfs_dist(grid, nodes[i], nodes[j]) for j in range(count)] for i in range(count)]
    if any(distance is None for row in pairwise for distance in row):
        return (False, None)
    best: int | None = None
    for order_of_foods in itertools.permutations(range(1, count - 1)):
        route = [0, *order_of_foods, count - 1]
        total = 0
        for index in range(len(route) - 1):
            leg = pairwise[route[index]][route[index + 1]]
            assert leg is not None
            total += leg
        if best is None or total < best:
            best = total
    return (best is not None, best)


def ucs_mask(oracle_scenario: OracleScenario) -> tuple[bool, int | None]:
    """Uniform-cost search over ``(food_mask, cell)`` states of my own packing."""
    grid = oracle_scenario["grid"]
    foods = sorted(oracle_scenario["foods"])
    bit_of = {food: index for index, food in enumerate(foods)}
    all_collected = (1 << len(foods)) - 1
    goal = oracle_scenario["goal"]
    start = oracle_scenario["start"]
    start_mask = 1 << bit_of[start] if start in bit_of else 0
    unreachable = 1 << 30
    best: dict[tuple[int, Cell], int] = {(start_mask, start): 0}
    frontier = [(0, 0, start_mask, start)]
    sequence = 1
    while frontier:
        cost, _, mask, cell = heappop(frontier)
        if cost > best.get((mask, cell), unreachable):
            continue
        if cell == goal and mask == all_collected:
            return (True, cost)
        for neighbour in grid.neighbours(cell):
            next_mask = mask | (1 << bit_of[neighbour]) if neighbour in bit_of else mask
            next_cost = cost + 1
            if next_cost < best.get((next_mask, neighbour), unreachable):
                best[(next_mask, neighbour)] = next_cost
                heappush(frontier, (next_cost, sequence, next_mask, neighbour))
                sequence += 1
    return (False, None)


@dataclass(frozen=True)
class FifoResult:
    """What a hand-written FIFO loop reports about one scenario."""

    found: bool
    path: tuple[Cell, ...]
    cost: int
    pops: int


def fifo_bfs(oracle_scenario: OracleScenario) -> FifoResult:
    """A hand-written FIFO breadth-first loop over ``(cell, collected)`` tuples."""
    grid = oracle_scenario["grid"]
    foods = oracle_scenario["foods"]
    goal = oracle_scenario["goal"]
    first: State = (oracle_scenario["start"], frozenset({oracle_scenario["start"]}) & foods)
    parents: dict[State, State | None] = {first: None}
    depth = {first: 0}
    queue = deque([first])
    pops = 0
    while queue:
        state = queue.popleft()
        pops += 1
        cell, collected = state
        if cell == goal and collected == foods:
            walk: list[Cell] = []
            cursor: State | None = state
            while cursor is not None:
                walk.append(cursor[0])
                cursor = parents[cursor]
            walk.reverse()
            return FifoResult(found=True, path=tuple(walk), cost=len(walk) - 1, pops=pops)
        for neighbour in grid.neighbours(cell):
            gathered = collected | {neighbour} if neighbour in foods else collected
            successor: State = (neighbour, frozenset(gathered))
            if successor in depth:
                continue
            depth[successor] = depth[state] + 1
            parents[successor] = state
            queue.append(successor)
    return FifoResult(found=False, path=(), cost=0, pops=pops)


def reachable_states(oracle_scenario: OracleScenario) -> set[State]:
    """Every ``(cell, collected)`` the start can stand in, found without the engine."""
    grid = oracle_scenario["grid"]
    foods = oracle_scenario["foods"]
    first: State = (oracle_scenario["start"], frozenset({oracle_scenario["start"]}) & foods)
    seen = {first}
    queue = deque([first])
    while queue:
        cell, collected = queue.popleft()
        for neighbour in grid.neighbours(cell):
            gathered = collected | {neighbour} if neighbour in foods else collected
            successor: State = (neighbour, frozenset(gathered))
            if successor not in seen:
                seen.add(successor)
                queue.append(successor)
    return seen


def true_remaining(
    oracle_scenario: OracleScenario, cell: Cell, collected: frozenset[Cell]
) -> int | None:
    """Exact moves still needed from one state, or ``None`` if no completion exists."""
    grid = oracle_scenario["grid"]
    foods = oracle_scenario["foods"]
    goal = oracle_scenario["goal"]
    first: State = (cell, collected)
    if cell == goal and collected == foods:
        return 0
    depth = {first: 0}
    queue = deque([first])
    while queue:
        state = queue.popleft()
        here, gathered_here = state
        for neighbour in grid.neighbours(here):
            gathered = gathered_here | {neighbour} if neighbour in foods else gathered_here
            successor: State = (neighbour, frozenset(gathered))
            if successor in depth:
                continue
            if neighbour == goal and successor[1] == foods:
                return depth[state] + 1
            depth[successor] = depth[state] + 1
            queue.append(successor)
    return None
