"""Behaviour of the optimal multi-goal breadth-first search.

Maps are drawn with columns as ``x`` (left to right) and rows as ``y`` (top to
bottom): ``S`` is the start, ``G`` the goal, ``F`` food and ``#`` a blocked cell.

This file is the named-behaviour net for the Phase 1 engine, so every expected
cost is hand-derived from the map in the docstring of its test: a lower bound the
asserted path reaches, or a count of the moves the map forces. Bulk optimality
against references is not checked here; it belongs to
:mod:`tests.unit.search.test_optimality_independent`, which compares the three
solvers against two references over far more maps than hand derivation could
cover.
"""

from collections.abc import Callable

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.result import SearchResult


def test_reaches_the_goal_without_food(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    grid = Grid(width=3, height=1, blocked=frozenset())
    scenario = AntScenario(grid=grid, start=Position(0, 0), goal=Position(2, 0), foods=frozenset())

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.path == (Position(0, 0), Position(1, 0), Position(2, 0))
    assert result.cost == 2
    assert result.expanded_states == 3


def test_collects_a_single_food_on_the_way(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    grid = Grid(width=5, height=1, blocked=frozenset())
    scenario = AntScenario(
        grid=grid, start=Position(0, 0), goal=Position(4, 0), foods=frozenset({Position(2, 0)})
    )

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.path == tuple(Position(x, 0) for x in range(5))
    assert result.cost == 4


def test_several_foods_are_collected_in_optimal_not_nearest_first_order(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """Three foods where collecting the nearest item first is two steps worse.

    F . F
    S . F
    # . G

    The food at (2, 1) is one step away, but collecting it first costs 8 steps.
    The optimal route detours upwards first and costs 6, which is the lower
    bound d(S, (0, 0)) + d((0, 0), G) = 2 + 4 for any route that visits (0, 0).
    """
    grid = Grid(width=3, height=3, blocked=frozenset({Position(0, 2)}))
    foods = frozenset({Position(0, 0), Position(2, 0), Position(2, 1)})
    scenario = AntScenario(grid=grid, start=Position(1, 1), goal=Position(2, 2), foods=foods)

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 6
    assert result.path.index(Position(2, 1)) > result.path.index(Position(0, 0))


def test_wall_forces_a_detour_through_its_single_gap(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """. # . . .
    S . # . G
    . . . . .

    The wall has a gap at (2, 2) only, so the route dips to y = 2: 4 + 2 = 6.
    """
    grid = Grid(width=5, height=3, blocked=frozenset({Position(2, 0), Position(2, 1)}))
    scenario = AntScenario(grid=grid, start=Position(0, 1), goal=Position(4, 1), foods=frozenset())

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 6
    assert Position(2, 2) in result.path


def test_unreachable_goal_reports_a_failure_with_expanded_states() -> None:
    """S . .
    # # #
    G . .
    """
    grid = Grid(
        width=3, height=3, blocked=frozenset({Position(0, 1), Position(1, 1), Position(2, 1)})
    )
    scenario = AntScenario(grid=grid, start=Position(0, 0), goal=Position(0, 2), foods=frozenset())

    result = solve_bfs(scenario)

    assert result.found is False
    assert result.path == ()
    assert result.cost == 0
    assert result.expanded_states == 3


def test_food_behind_a_wall_reports_a_failure() -> None:
    """The food sits in a pocket the ant can never reach.

    S # F
    G # .
    """
    grid = Grid(width=3, height=2, blocked=frozenset({Position(1, 0), Position(1, 1)}))
    scenario = AntScenario(
        grid=grid, start=Position(0, 0), goal=Position(0, 1), foods=frozenset({Position(2, 1)})
    )

    result = solve_bfs(scenario)

    assert result.found is False
    assert result.path == ()
    assert result.cost == 0
    assert result.expanded_states == 2


def test_start_on_the_goal_without_food_costs_nothing(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    grid = Grid(width=3, height=3, blocked=frozenset())
    scenario = AntScenario(grid=grid, start=Position(1, 1), goal=Position(1, 1), foods=frozenset())

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.path == (Position(1, 1),)
    assert result.cost == 0
    assert result.expanded_states == 1


def test_start_on_the_goal_with_food_leaves_and_comes_back(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """The goal cell is only accepted once the food has been collected."""
    grid = Grid(width=3, height=3, blocked=frozenset())
    scenario = AntScenario(
        grid=grid,
        start=Position(1, 1),
        goal=Position(1, 1),
        foods=frozenset({Position(0, 0)}),
    )

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.path[0] == Position(1, 1) == result.path[-1]
    assert len(result.path) == 5
    assert result.cost == 4


def test_start_on_the_goal_with_two_foods_visits_both_corners(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    grid = Grid(width=3, height=3, blocked=frozenset())
    scenario = AntScenario(
        grid=grid,
        start=Position(1, 1),
        goal=Position(1, 1),
        foods=frozenset({Position(0, 0), Position(2, 2)}),
    )

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 8
    assert len(result.path) == 9


def test_same_cell_must_be_revisited_with_different_collected_food(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """The start cell is entered twice, the second time carrying food.

    F # F
    . S .
    . G .

    (1, 1) is blocked, so the only walk to the second food leaves the start cell
    (1, 0) and returns to it after picking up (0, 0). The optimum is 6 steps; a
    search that remembers visited cells only would stop on the goal after 4 steps
    with nothing collected.
    """
    grid = Grid(width=3, height=3, blocked=frozenset({Position(1, 1)}))
    scenario = AntScenario(
        grid=grid,
        start=Position(1, 0),
        goal=Position(1, 2),
        foods=frozenset({Position(0, 0), Position(2, 0)}),
    )

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 6
    assert result.path.count(Position(1, 0)) == 2


def test_walking_through_the_goal_before_collecting_food_is_allowed() -> None:
    """The goal cell is the only doorway to the food, so it is crossed twice.

    S . G
    # # .
    # # F
    """
    grid = Grid(
        width=3,
        height=3,
        blocked=frozenset({Position(0, 1), Position(1, 1), Position(0, 2), Position(1, 2)}),
    )
    scenario = AntScenario(
        grid=grid,
        start=Position(0, 0),
        goal=Position(2, 0),
        foods=frozenset({Position(2, 2)}),
    )

    result = solve_bfs(scenario)

    assert result.found is True
    assert result.path == (
        Position(0, 0),
        Position(1, 0),
        Position(2, 0),
        Position(2, 1),
        Position(2, 2),
        Position(2, 1),
        Position(2, 0),
    )
    assert result.cost == 6
    assert result.path[-1] == scenario.goal


def test_food_under_the_start_cell_is_collected_immediately(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """Standing on food counts as picking it up, so no return trip is needed."""
    grid = Grid(width=5, height=1, blocked=frozenset())
    scenario = AntScenario(
        grid=grid, start=Position(0, 0), goal=Position(4, 0), foods=frozenset({Position(0, 0)})
    )

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 4


def test_start_surrounded_by_walls_expands_only_the_start_state() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset({Position(1, 0), Position(0, 1)}))
    scenario = AntScenario(grid=grid, start=Position(0, 0), goal=Position(2, 2), foods=frozenset())

    result = solve_bfs(scenario)

    assert result.found is False
    assert result.expanded_states == 1


def test_blocked_neighbor_of_the_start_is_avoided(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    grid = Grid(width=3, height=3, blocked=frozenset({Position(1, 0)}))
    scenario = AntScenario(grid=grid, start=Position(0, 0), goal=Position(2, 2), foods=frozenset())

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 4
    assert Position(1, 0) not in result.path
