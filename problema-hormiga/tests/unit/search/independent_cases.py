"""Scenario sets for the independent search verification, built from raw tuples.

Every set is either exhaustive over a small grid or drawn from a fixed seed, so a failure is
reproducible. The degenerate cases are the rules of the problem stated one at a time: the start
that is already the goal, food on the start, food on the goal, a start walled in, a food in a
sealed pocket, and a goal in a sealed pocket.

The sweeps are returned as plain lists and looped over *inside* a test rather than fed to
``@pytest.mark.parametrize``. A sweep is thousands of maps; enumerating it into collected test
ids would turn one property into thousands of collected cases without checking a single
additional map, and would make a failure a 3,000-line report instead of a named scenario.
"""

from __future__ import annotations

import itertools
from random import Random

from independent_oracle import Cell, OracleGrid, OracleScenario, make

__all__ = [
    "DEGENERATE_CASES",
    "Discrepancies",
    "describe",
    "exhaustive",
    "random_maps",
    "sample",
    "sweep",
]


def describe(oracle_scenario: OracleScenario) -> str:
    """A one-line rendering of a scenario, for a failure message."""
    grid = oracle_scenario["grid"]
    return (
        f"{grid.width}x{grid.height} walls={sorted(grid.walls)} "
        f"start={oracle_scenario['start']} goal={oracle_scenario['goal']} "
        f"foods={sorted(oracle_scenario['foods'])}"
    )


def exhaustive(
    width: int, height: int, walls: frozenset[Cell], nfoods: int
) -> list[OracleScenario]:
    """Every start/goal/food combination of one grid, walls fixed.

    ``start`` and ``goal`` are drawn as an ordered pair so ``start == goal`` is included; the
    food count is fixed and sampled without repetition, so a food may land on the start or on
    the goal, which is what the problem allows.
    """
    grid = OracleGrid(width, height, frozenset(walls))
    cells = [(x, y) for y in range(height) for x in range(width) if grid.walkable((x, y))]
    return [
        make(width, height, walls, start, goal, frozenset(foods))
        for start, goal in itertools.permutations(cells, 2)
        for foods in itertools.combinations(cells, nfoods)
    ]


def random_maps(
    count: int,
    seed: int,
    sizes: tuple[tuple[int, int], ...],
    density: float,
    maxfoods: int = 4,
) -> list[OracleScenario]:
    """Draw ``count`` maps of one size at one obstacle density, from a fixed seed."""
    generator = Random(seed)
    drawn: list[OracleScenario] = []
    while len(drawn) < count:
        width, height = generator.choice(sizes)
        cells = [(x, y) for y in range(height) for x in range(width)]
        walls = frozenset(cell for cell in cells if generator.random() < density)
        grid = OracleGrid(width, height, walls)
        free = [cell for cell in cells if grid.walkable(cell)]
        if len(free) < 2:
            continue
        start, goal = generator.sample(free, 2)
        wanted = generator.randint(0, maxfoods)
        foods = frozenset(generator.sample(free, min(wanted, len(free))))
        drawn.append(make(width, height, walls, start, goal, foods))
    return drawn


def sweep(*blocks: list[OracleScenario] | tuple[str, list[OracleScenario]]) -> list[OracleScenario]:
    """Concatenate several map sets into one list to loop over."""
    combined: list[OracleScenario] = []
    for block in blocks:
        combined.extend(block[1] if isinstance(block, tuple) else block)
    return combined


DEGENERATE_CASES: list[tuple[str, OracleScenario]] = [
    ("start-is-goal", make(3, 3, frozenset(), (1, 1), (1, 1))),
    (
        "start-is-goal-with-food-on-start",
        make(3, 3, frozenset(), (1, 1), (1, 1), frozenset({(1, 1)})),
    ),
    ("food-on-start", make(5, 1, frozenset(), (0, 0), (4, 0), frozenset({(0, 0)}))),
    ("food-on-goal", make(3, 3, frozenset(), (0, 0), (2, 2), frozenset({(2, 2)}))),
    (
        "start-is-goal-is-food",
        make(1, 1, frozenset(), (0, 0), (0, 0), frozenset({(0, 0)})),
    ),
    (
        "start-walled-in",
        make(3, 3, frozenset({(1, 0), (1, 1), (0, 2), (1, 2)}), (0, 1), (2, 2)),
    ),
    (
        "food-in-a-sealed-pocket",
        make(3, 2, frozenset({(1, 0), (1, 1)}), (0, 0), (0, 1), frozenset({(2, 1)})),
    ),
    (
        "goal-in-a-sealed-pocket",
        make(4, 3, frozenset({(1, 0), (1, 1), (1, 2)}), (0, 1), (3, 0), frozenset({(3, 2)})),
    ),
    (
        "goal-is-the-starts-only-neighbour",
        make(3, 1, frozenset(), (1, 0), (0, 0)),
    ),
]


class Discrepancies:
    """Collect what went wrong across a sweep so one failure reports everything, not the first.

    A sweep is thousands of maps; aborting on the first bad one would hide whether it is one
    map or a whole family of them. Failures are therefore accumulated and reported together,
    capped so a systematic break does not produce a ten-thousand-line message.
    """

    CAP = 5

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.total = 0

    def add(self, scenario: OracleScenario, problem: str) -> None:
        """Record that ``scenario`` broke a property."""
        self.total += 1
        if len(self.messages) < self.CAP:
            self.messages.append(f"{problem} :: {describe(scenario)}")

    def raise_if_any(self, property_name: str) -> None:
        """Report every collected failure, naming the property and the count."""
        if not self.total:
            return
        shown = "\n  ".join(self.messages)
        extra = f"\n  ... and {self.total - self.CAP} more" if self.total > self.CAP else ""
        raise AssertionError(
            f"{property_name}: {self.total} of the swept scenarios disagree "
            f"(first {len(self.messages)}):\n  {shown}{extra}"
        )


def sample(maps: list[OracleScenario], count: int, seed: int) -> list[OracleScenario]:
    """Take ``count`` maps from ``maps`` with a fixed seed, or all of them if there are fewer.

    Used where a whole exhaustive family is far larger than the property needs - 3x4 with two
    foods is 8,712 maps per wall pattern - so the sample is drawn once from the full family and
    the count is written down next to it, rather than trimmed silently.
    """
    if len(maps) <= count:
        return maps
    return Random(seed).sample(maps, count)
