"""Dijkstra and A* measured against the breadth-first optimality oracle.

``solve_bfs`` is the oracle: it is the algorithm this suite has already cross-checked
against three independent references, and it is optimal because every move costs 1. A
new solver is optimal on this problem exactly when it agrees with the oracle on
``found`` and on ``cost``. The returned *path* is compared only where equality is
guaranteed, because A* is free to break ties between equal-length walks differently -
asserting path equality from A* would assert something the algorithm never promised.

Maps are drawn with columns as ``x`` left to right and rows as ``y`` top to bottom:
``S`` is the start, ``G`` the goal, ``F`` food and ``#`` a blocked cell.
"""

from collections.abc import Callable

import pytest
from conftest import SCENARIO_CASES, SMALL_RANDOM_CASES, SOLVERS, build_scenario

from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.algorithms import SearchAlgorithm, new_runner, solve
from ant_pathfinding.search.astar import solve_astar
from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.dijkstra import solve_dijkstra
from ant_pathfinding.search.progress import SearchOutcome
from ant_pathfinding.search.result import SearchResult


@SOLVERS
@pytest.mark.parametrize("scenario", SMALL_RANDOM_CASES)
def test_matches_the_oracle_on_small_random_maps(
    solver: Callable[[AntScenario], SearchResult], scenario: AntScenario
) -> None:
    """Random small maps: solvability and cost are the oracle's.

    Deliberately not the path. Dijkstra is guaranteed to reproduce the breadth-first
    walk exactly and is compared on the path further down; A* is not, so only the
    pair the optimality claim is about is compared here.
    """
    oracle = solve_bfs(scenario)

    result = solver(scenario)

    assert (result.found, result.cost) == (oracle.found, oracle.cost), scenario
    assert bool(result.path) is result.found


@SOLVERS
@pytest.mark.parametrize("scenario", SCENARIO_CASES)
def test_matches_the_oracle_on_the_hand_designed_matrix(
    solver: Callable[[AntScenario], SearchResult],
    scenario: AntScenario,
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """Every rule of the problem, from no food at all to an ant walled in.

    A reported failure must be a real impossibility, so the unsolvable cases are
    checked for an empty path and no cost as well as for agreement with the oracle.
    """
    oracle = solve_bfs(scenario)

    result = solver(scenario)

    assert (result.found, result.cost) == (oracle.found, oracle.cost), scenario
    if result.found:
        assert_valid_solution(scenario, result)
    else:
        assert result.path == ()
        assert result.cost == 0
        assert result.expanded_states >= 1


@pytest.mark.parametrize("scenario", SCENARIO_CASES)
def test_uniform_cost_search_agrees_with_breadth_first_search_exactly(
    scenario: AntScenario,
) -> None:
    """Dijkstra *is* breadth-first search on a unit-cost grid, and that is pinned here.

    Not only the answer but the run itself: the same path and the same
    ``expanded_states``, which can only agree if both algorithms pop the states in the
    same order.
    """
    breadth_first = solve_bfs(scenario)
    uniform_cost = solve_dijkstra(scenario)

    assert uniform_cost.path == breadth_first.path
    assert uniform_cost.expanded_states == breadth_first.expanded_states
    assert uniform_cost == breadth_first


def test_astar_expands_far_less_than_uniform_cost_where_the_bound_prunes() -> None:
    """A* expands exactly the states of an optimal walk; uniform cost explores the map.

    ``S . . . .
    . . . . .
    . . . . .
    F . . . G``

    The optimum is 7 moves: any walk has to reach the food and then the goal, so it
    costs at least ``d(S, F) + d(F, G) = 3 + 4``, and the left column followed by the
    bottom row attains that bound. Every state of that walk has ``g + h = 7`` because
    the estimate is exact along it, and every state off the walk that A* discovers
    has ``g + h`` of at least 9, so A* can never prefer one: it expands the eight
    states of the optimal walk and nothing else. Uniform cost has no estimate to prune
    with, so it expands every state within the cost bound - every cell of the map,
    once for each collected-food subset.
    """
    scenario = build_scenario(5, 4, [], start=(0, 0), goal=(4, 3), foods=[(0, 3)])

    uniform_cost = solve_dijkstra(scenario)
    astar = solve_astar(scenario)

    assert (astar.found, astar.cost) == (True, 7)
    assert astar.cost == 3 + 4
    assert astar.expanded_states == 8 == astar.cost + 1
    assert astar.expanded_states * 3 < uniform_cost.expanded_states


@pytest.mark.parametrize(
    ("algorithm", "entry_point"),
    [
        (SearchAlgorithm.BFS, solve_bfs),
        (SearchAlgorithm.DIJKSTRA, solve_dijkstra),
        (SearchAlgorithm.ASTAR, solve_astar),
    ],
)
def test_solving_by_name_matches_the_direct_entry_point(
    algorithm: SearchAlgorithm,
    entry_point: Callable[[AntScenario], SearchResult],
) -> None:
    """Selecting an algorithm by name is not a second implementation of it.

    The map has two foods and a wall, so the three algorithms have something to
    disagree about if they ever were going to.
    """
    scenario = build_scenario(
        4, 3, [Position(1, 1)], start=(0, 0), goal=(3, 2), foods=[(3, 0), (0, 2)]
    )

    assert solve(algorithm, scenario) == entry_point(scenario)


def test_the_algorithm_enum_lists_exactly_the_three_searches() -> None:
    """The selection a caller may make is a closed, named set."""
    assert [member.value for member in SearchAlgorithm] == ["bfs", "dijkstra", "astar"]


def test_two_runners_over_one_scenario_share_nothing() -> None:
    """Runs are independent: running one to the end cannot advance the other.

    Two runners built from the same immutable scenario must not share a frontier, a
    cost table, a parent map or a counter - otherwise a second view of the same map
    would silently corrupt the first.
    """
    scenario = build_scenario(4, 3, [], start=(0, 0), goal=(3, 2), foods=[(3, 0), (0, 2)])

    first = new_runner(SearchAlgorithm.BFS, scenario)
    second = new_runner(SearchAlgorithm.ASTAR, scenario)
    untouched = new_runner(SearchAlgorithm.ASTAR, scenario)

    assert second.statistics == untouched.statistics
    assert second.statistics.expanded_states == 0

    first.step()
    first.step()
    assert second.statistics == untouched.statistics, "the second runner moved"
    assert first.statistics.expanded_states == 2

    from_astar = second.run_to_completion()
    assert first.statistics.expanded_states == 2, "running one run advanced the other"
    assert first.outcome is SearchOutcome.RUNNING
    assert from_astar.cost == solve_bfs(scenario).cost
    assert first.run_to_completion() == solve_bfs(scenario)
