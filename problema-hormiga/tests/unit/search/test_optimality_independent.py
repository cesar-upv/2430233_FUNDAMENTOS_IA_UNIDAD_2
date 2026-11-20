"""The three solvers against two references that do not share the engine's structure.

``solve_bfs``, ``solve_dijkstra`` and ``solve_astar`` each claim the same ``(found, cost)``
pair. The claim is checked against references written in :mod:`independent_oracle`: one
minimises over every order in which the food could be visited without ever building a state
space, the other packs the collected food into an integer mask and runs uniform-cost search.
Three solvers agreeing with each other would prove nothing; a solver agreeing with a reference
it shares no code with does.

**On the shape of this file.** The sweeps are looped over inside each test rather than fed to
``@pytest.mark.parametrize``. A sweep is thousands of maps; enumerating it into collected test
ids checks no additional map and turns one property into thousands of collected cases, so the
volume lives in the loop and only the genuinely discrete axis - the three algorithms - is
parametrized. Failures are accumulated by :class:`~independent_cases.Discrepancies` so one
broken map does not hide the next, and the report names the scenario.

A returned path is also checked to be a real walk - it starts on the start cell, ends on the
goal cell, moves one orthogonal step at a time between walkable cells, passes over every food,
and reports a cost equal to the number of moves actually walked.

**Deliberate duplication.** :func:`_walk_problem` is a third spelling of the path-validity check,
the other two being the ``assert_valid_solution`` fixture in ``conftest`` and the hand-written
assertions in ``test_bfs_adversarial.py``. Sharing one of them would mean the independent oracle
and the project tests agreed by construction, which is the agreement this file exists to replace
with something real.
"""

from itertools import pairwise

import pytest
from independent_cases import (
    DEGENERATE_CASES,
    Discrepancies,
    describe,
    exhaustive,
    random_maps,
    sample,
    sweep,
)
from independent_oracle import OracleScenario, held_karp, to_scenario, ucs_mask

from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.astar import solve_astar
from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.dijkstra import solve_dijkstra

SOLVERS = [
    pytest.param(solve_bfs, id="bfs"),
    pytest.param(solve_dijkstra, id="dijkstra"),
    pytest.param(solve_astar, id="astar"),
]
"""Every solver that must answer the same optimal ``(found, cost)`` pair."""

WALLS_3x4 = [
    ("open", frozenset()),
    ("one-wall-top", frozenset({(1, 0)})),
    ("one-wall-middle", frozenset({(1, 1)})),
    ("two-walls", frozenset({(0, 1), (2, 2)})),
    ("a-column", frozenset({(1, 0), (1, 1)})),
]
"""Five wall patterns of a 3x4 grid, so the maps are never all open."""

SMALL_MAPS = sweep(
    ("2x2-no-food", exhaustive(2, 2, frozenset(), 0)),
    ("2x2-one-food", exhaustive(2, 2, frozenset(), 1)),
    ("2x2-two-foods", exhaustive(2, 2, frozenset(), 2)),
    ("3x3-no-food", exhaustive(3, 3, frozenset(), 0)),
    ("3x3-one-food", exhaustive(3, 3, frozenset(), 1)),
)
"""852 maps, enumerable in full, so nothing here rests on a sample."""

TWO_FOOD_MAPS = sweep(
    ("3x3-full", exhaustive(3, 3, frozenset(), 2)),
    *(
        (f"3x4-{label}-600-of-8712", sample(exhaustive(3, 4, walls, 2), 600, seed=seed))
        for label, walls in WALLS_3x4
        for seed in (201, 202)
    ),
)
"""Two foods over every open 3x3 and 600 sampled maps of each walled 3x4.

    A 3x4 grid with two foods holds 8,712 maps, so each of the five wall patterns contributes a
    fixed-seed sample of 600 rather than the whole family; the 3x3 family is small enough to take
    whole. 8,592 maps in total, against 40,216 when every family was taken whole - the sample is
    smaller, and it is a sample of engine runs, which are the expensive part of this suite.
    """

RANDOM_MAPS = sweep(
    *(
        (
            f"{size[0]}x{size[1]}-{int(density * 100)}pc",
            random_maps(100, seed=seed, sizes=(size,), density=density),
        )
        for size in ((4, 4), (5, 4))
        for density in (0.0, 0.1, 0.2, 0.3)
        for seed in (101, 102)
    ),
)
"""1,600 randomized maps at obstacle densities 0% to 30%, zero to four foods."""

ALL_MAPS = sweep(
    SMALL_MAPS, TWO_FOOD_MAPS, RANDOM_MAPS, ("degenerate", [case for _, case in DEGENERATE_CASES])
)


def _expected(oracle_scenario: OracleScenario) -> tuple[bool, int]:
    """The optimum from the two references, which must agree with each other first.

    Checking them against each other is what separates "the engine is wrong" from "the reference
    is wrong" in a failure report.
    """
    by_order, cost_by_order = held_karp(oracle_scenario)
    by_mask, cost_by_mask = ucs_mask(oracle_scenario)
    assert (by_order, cost_by_order) == (by_mask, cost_by_mask), (
        f"the two independent references disagree on {describe(oracle_scenario)}"
    )
    return (by_order, cost_by_order if by_order else 0)


def _walk_problem(scenario: AntScenario, path: tuple) -> str | None:
    """Describe how ``path`` fails to be a real walk, or ``None`` when it is one."""
    cells = [(position.x, position.y) for position in path]
    if cells[0] != (scenario.start.x, scenario.start.y):
        return f"the walk starts at {cells[0]}, not at the start cell"
    if cells[-1] != (scenario.goal.x, scenario.goal.y):
        return f"the walk ends at {cells[-1]}, not on the goal cell"
    for position in path:
        if not scenario.grid.is_walkable(position):
            return f"the walk stands on {position}, which is not walkable"
    for previous, current in pairwise(cells):
        if abs(previous[0] - current[0]) + abs(previous[1] - current[1]) != 1:
            return f"non-orthogonal step from {previous} to {current}"
    if not set(scenario.foods) <= set(path):
        return "the walk misses a food item"
    return None


def _check_map(solver, oracle_scenario: OracleScenario, problems: Discrepancies) -> None:
    """Run ``solver`` on one map and record how it differs from the reference, if at all."""
    scenario = to_scenario(oracle_scenario)
    result = solver(scenario)
    expected_found, expected_cost = _expected(oracle_scenario)

    if (result.found, result.cost) != (expected_found, expected_cost):
        problems.add(
            oracle_scenario,
            f"{solver.__name__} reported (found={result.found}, cost={result.cost}), "
            f"the references say (found={expected_found}, cost={expected_cost})",
        )
        return
    if result.found:
        problem = _walk_problem(scenario, result.path)
        if problem is not None:
            problems.add(oracle_scenario, problem)
        if len(result.path) - 1 != result.cost:
            problems.add(
                oracle_scenario,
                f"reported cost {result.cost} is not the {len(result.path) - 1} moves walked",
            )
    elif result.path or result.cost:
        problems.add(oracle_scenario, "a failed result carries a path or a non-zero cost")


@pytest.mark.parametrize("solver", SOLVERS)
def test_every_small_map_is_solved_optimally(solver) -> None:
    """Every 2x2 map and every open 3x3 map with up to one food, all start/goal pairs.

    Small enough to enumerate in full, so nothing here rests on a sample. Food may land on the
    start or on the goal, which is what the problem allows.
    """
    problems = Discrepancies()
    for oracle_scenario in SMALL_MAPS:
        _check_map(solver, oracle_scenario, problems)

    problems.raise_if_any("every small map is solved optimally")
    assert len(SMALL_MAPS) == 852


@pytest.mark.parametrize("solver", SOLVERS)
def test_two_food_maps_are_solved_optimally_open_and_walled(solver) -> None:
    """Two foods over every 3x3 and over five wall patterns of a 3x4.

    Two foods is where a greedy "walk to the nearest one" strategy first goes wrong, so it is
    the case that separates a real optimum from a plausible-looking one. A wall can seal the
    goal off, seal a food off, or only force a detour; all three have to come back as the
    answer the references give.
    """
    problems = Discrepancies()
    for oracle_scenario in TWO_FOOD_MAPS:
        _check_map(solver, oracle_scenario, problems)

    problems.raise_if_any("two-food maps are solved optimally")
    assert len(TWO_FOOD_MAPS) == 8_592


@pytest.mark.parametrize("solver", SOLVERS)
def test_random_maps_are_solved_optimally(solver) -> None:
    """Randomized 4x4 and 5x4 maps at obstacle densities 0% to 30%, zero to four foods."""
    problems = Discrepancies()
    for oracle_scenario in RANDOM_MAPS:
        _check_map(solver, oracle_scenario, problems)

    problems.raise_if_any("random maps are solved optimally")
    assert len(RANDOM_MAPS) == 1600


@pytest.mark.parametrize("case", DEGENERATE_CASES, ids=[name for name, _ in DEGENERATE_CASES])
def test_each_degenerate_rule_is_named_and_holds(case: tuple[str, OracleScenario]) -> None:
    """One readable case per rule of the problem, so a break names the rule it broke.

    The sweep covers these maps too; this exists for the failure message, not for the coverage.
    """
    _, oracle_scenario = case
    scenario = to_scenario(oracle_scenario)

    result = solve_bfs(scenario)
    expected_found, expected_cost = _expected(oracle_scenario)

    assert (result.found, result.cost) == (expected_found, expected_cost), describe(oracle_scenario)
    if result.found:
        assert _walk_problem(scenario, result.path) is None
    else:
        assert result.path == () and result.cost == 0, describe(oracle_scenario)
        assert result.expanded_states >= 1, describe(oracle_scenario)


def test_the_two_references_agree_with_each_other_on_the_whole_sweep() -> None:
    """The oracle set is only a test if its references are themselves consistent.

    Cheap to assert directly over the same maps the optimality tests use, and it separates "the
    engine is wrong" from "the reference is wrong" when a failure shows up.
    """
    problems = Discrepancies()
    for oracle_scenario in ALL_MAPS:
        if held_karp(oracle_scenario) != ucs_mask(oracle_scenario):
            problems.add(oracle_scenario, "the two references disagree with each other")

    problems.raise_if_any("the two references agree with each other")
