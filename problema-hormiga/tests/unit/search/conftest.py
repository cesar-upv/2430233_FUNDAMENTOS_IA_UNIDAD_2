"""Shared assertions and scenario sets for the search tests."""

from collections.abc import Callable, Collection
from random import Random

import pytest
from _pytest.mark.structures import ParameterSet

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.astar import solve_astar
from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.dijkstra import solve_dijkstra
from ant_pathfinding.search.result import SearchResult

SOLVERS = pytest.mark.parametrize(
    "solver", [solve_bfs, solve_dijkstra, solve_astar], ids=["bfs", "dijkstra", "astar"]
)
"""Every solver that must answer the same optimal ``(found, cost)`` pair.

Breadth-first search is the optimality oracle of this suite, so Dijkstra and A* are
checked against it rather than against hand-written expectations.
"""


@pytest.fixture
def assert_valid_solution() -> Callable[[AntScenario, SearchResult], None]:
    """Return a checker that validates a successful result against its scenario.

    A valid solution starts on the start cell, ends on the goal cell, moves only
    between walkable orthogonal neighbors, costs one unit per move and walks over
    every food item, which is what collecting food on entry means.
    """

    def check(scenario: AntScenario, result: SearchResult) -> None:
        assert result.found is True
        assert result.path[0] == scenario.start
        assert result.path[-1] == scenario.goal
        assert result.cost == len(result.path) - 1
        assert result.expanded_states > 0
        assert all(scenario.grid.is_walkable(position) for position in result.path)
        assert set(scenario.foods) <= set(result.path)
        for previous, current in zip(result.path, result.path[1:], strict=False):
            step = abs(previous.x - current.x) + abs(previous.y - current.y)
            assert step == 1, f"non-orthogonal step from {previous} to {current}"

    return check


def build_scenario(
    width: int,
    height: int,
    blocked: Collection[Position],
    start: tuple[int, int],
    goal: tuple[int, int],
    foods: Collection[tuple[int, int]] = (),
) -> AntScenario:
    """Build a scenario from readable ``(x, y)`` pairs, as the maps below are drawn."""
    return AntScenario(
        grid=Grid(width=width, height=height, blocked=frozenset(blocked)),
        start=Position(*start),
        goal=Position(*goal),
        foods=frozenset(Position(*cell) for cell in foods),
    )


def _build_small_random_scenarios() -> list[AntScenario]:
    """Draw twenty-four small valid scenarios from one fixed seed.

    Grids of two to four cells a side, at most a fifth of them blocked and zero to
    three foods, which keeps every state space tiny while still covering unsolvable
    scenarios, unreachable food and unreachable goals. A draw that would leave fewer
    than two walkable cells - and so no distinct start and goal - is discarded.
    """
    generator = Random(20_261_005)
    scenarios: list[AntScenario] = []
    while len(scenarios) < 24:
        width = generator.randint(2, 4)
        height = generator.randint(2, 4)
        cells = [Position(x, y) for y in range(height) for x in range(width)]
        blocked = frozenset(cell for cell in cells if generator.random() < 0.2)
        grid = Grid(width=width, height=height, blocked=blocked)
        free = [cell for cell in cells if grid.is_walkable(cell)]
        if len(free) < 2:
            continue
        start, goal = generator.sample(free, 2)
        foods = frozenset(generator.sample(free, generator.randint(0, 3)))
        scenarios.append(AntScenario(grid=grid, start=start, goal=goal, foods=foods))
    return scenarios


SMALL_RANDOM_SCENARIOS: list[AntScenario] = _build_small_random_scenarios()
"""The seeded scenario set, built once at import so a fixed seed really is fixed."""

SMALL_RANDOM_CASES: list[ParameterSet] = [
    pytest.param(scenario, id=f"map-{index:02d}")
    for index, scenario in enumerate(SMALL_RANDOM_SCENARIOS)
]
"""The same scenarios as parameter sets, so a failure names the map that failed."""


@pytest.fixture
def small_random_scenarios() -> list[AntScenario]:
    """The seeded small scenario set, shared by every test that sweeps scenarios.

    Fixed seed, so a failure is reproducible and every test reasons about the same
    maps instead of about its own private draw.
    """
    return SMALL_RANDOM_SCENARIOS


SCENARIO_CASES: list[ParameterSet] = [
    # S . G
    pytest.param(
        build_scenario(3, 1, [], start=(0, 0), goal=(2, 0)),
        id="no-food",
    ),
    # S . F . G
    pytest.param(
        build_scenario(5, 1, [], start=(0, 0), goal=(4, 0), foods=[(2, 0)]),
        id="food-on-the-way",
    ),
    # F . F
    # S . F
    # # . G
    pytest.param(
        build_scenario(
            3, 3, [Position(0, 2)], start=(1, 1), goal=(2, 2), foods=[(0, 0), (2, 0), (2, 1)]
        ),
        id="nearest-food-first-is-suboptimal",
    ),
    # S # F
    # G # .
    pytest.param(
        build_scenario(
            3, 2, [Position(1, 0), Position(1, 1)], start=(0, 0), goal=(0, 1), foods=[(2, 1)]
        ),
        id="unreachable-food",
    ),
    # S . .
    # # # #
    # G . .
    pytest.param(
        build_scenario(
            3,
            3,
            [Position(0, 1), Position(1, 1), Position(2, 1)],
            start=(0, 0),
            goal=(0, 2),
        ),
        id="unreachable-goal",
    ),
    # . # . G
    # S # . .
    # . # . F
    pytest.param(
        build_scenario(
            4,
            3,
            [Position(1, 0), Position(1, 1), Position(1, 2)],
            start=(0, 1),
            goal=(3, 0),
            foods=[(3, 2)],
        ),
        id="unreachable-food-and-goal",
    ),
    # . . .
    # . S .
    # . G .
    pytest.param(
        build_scenario(3, 3, [], start=(1, 1), goal=(1, 1)),
        id="start-is-goal-without-food",
    ),
    # . . .
    # . S .
    # . G .
    # with one food in the corner
    pytest.param(
        build_scenario(3, 3, [], start=(1, 1), goal=(1, 1), foods=[(0, 0)]),
        id="start-is-goal-with-food",
    ),
    # F . . . G
    pytest.param(
        build_scenario(5, 1, [], start=(0, 0), goal=(4, 0), foods=[(0, 0)]),
        id="food-on-start",
    ),
    # . . .
    # . . .
    # F F G
    pytest.param(
        build_scenario(3, 3, [], start=(0, 0), goal=(2, 2), foods=[(2, 2)]),
        id="food-on-goal",
    ),
    # S   every cell of this grid is the start, the goal and the only food
    pytest.param(
        build_scenario(1, 1, [], start=(0, 0), goal=(0, 0), foods=[(0, 0)]),
        id="start-is-goal-is-food",
    ),
    # # . .
    # S # .
    # # # G
    pytest.param(
        build_scenario(
            3,
            3,
            [Position(1, 0), Position(1, 1), Position(0, 2), Position(1, 2)],
            start=(0, 1),
            goal=(2, 2),
        ),
        id="start-walled-in",
    ),
]
"""One hand-designed scenario per rule of the problem, each with a readable id."""


@pytest.fixture
def scenario_cases() -> list[ParameterSet]:
    """The hand-designed scenario matrix as parameter sets, ids included.

    No expected answer comes from here: tests compare every solver against the
    breadth-first oracle and validate the paths that are returned.
    """
    return SCENARIO_CASES
