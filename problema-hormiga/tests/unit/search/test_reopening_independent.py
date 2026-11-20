"""What happens when the engine reopens a state instead of closing it.

``SearchRunner`` never closes a state permanently: a state whose cost is improved after it was
expanded is pushed again and expanded again. That is what keeps A* optimal under an estimate that
is admissible but not consistent, and it is the part of the engine where a mistake would show up
as either a suboptimal path or a path that is not a walk. Both are pinned here, with estimates
that force the reopening rather than waiting for the default one to happen to produce it.

The sweeps are looped over inside each test; the three adversarial estimates are the discrete axis
and stay parametrized, because which estimate produced a failure is the first thing to know.

**Deliberate duplication.** :func:`_walk_problem` and the oracle-to-``SearchState`` bridge are
re-implemented here rather than imported from ``test_heuristics_independent`` or
``test_optimality_independent``, which carry their own copies: an independent oracle must not share
code with the code under test, or one wrong assumption could satisfy both sides at once.
"""

from itertools import pairwise

import pytest
from independent_cases import (
    Discrepancies,
    describe,
    exhaustive,
    random_maps,
    sample,
    sweep,
)
from independent_oracle import (
    OracleGrid,
    OracleScenario,
    held_karp,
    reachable_states,
    to_scenario,
    true_remaining,
    ucs_mask,
)

from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.heuristics import Heuristic, manhattan_mst
from ant_pathfinding.search.runner import SearchRunner
from ant_pathfinding.search.state import SearchState


def _detour(scenario: AntScenario, state: SearchState) -> int:
    """Prefer the long way round, so a state is improved before it is ever popped."""
    return 1000 - (
        abs(state.position.x - scenario.start.x) + abs(state.position.y - scenario.start.y)
    )


def _oscillate(scenario: AntScenario, state: SearchState) -> int:
    """An arbitrary, wildly inconsistent estimate, admissible nowhere."""
    return (state.position.x * 7 + state.position.y * 13 + 5 * len(state.collected)) % 23


def _reward_completion(scenario: AntScenario, state: SearchState) -> int:
    """Reward a state for having collected everything; otherwise blind."""
    return 0 if state.collected == scenario.foods else 50


def _goal_or_pending(scenario: AntScenario, state: SearchState) -> int:
    """Distance to the goal while food is pending, else one move per food left.

    Admissible - the true remaining cost is at least the straight-line distance to the goal and at
    least one move per food item still to collect - and inconsistent, because the estimate switches
    between two lower bounds from one move to the next.
    """
    pending = len(scenario.foods - state.collected)
    to_goal = abs(state.position.x - scenario.goal.x) + abs(state.position.y - scenario.goal.y)
    return to_goal if pending > 1 else pending


INCONSISTENT_ESTIMATES = [
    pytest.param(_detour, id="detour"),
    pytest.param(_oscillate, id="oscillate"),
    pytest.param(_reward_completion, id="reward-completion"),
    pytest.param(_goal_or_pending, id="goal-or-pending"),
]
"""Four estimates that make the engine improve, reopen and re-expand states.

    The first three are inadmissible, so a wrong answer from them is the estimate's fault rather
    than the engine's. The fourth is admissible, which makes it the interesting one: an admissible
    estimate that reopens must still return the optimum.
    """

REOPENING_ESTIMATES = [
    pytest.param(_oscillate, id="oscillate"),
    pytest.param(_reward_completion, id="reward-completion"),
    pytest.param(_goal_or_pending, id="goal-or-pending"),
]
"""The subset that is measured to re-expand, measured over both map lists.

    ``_detour`` improves states but does so before they are ever popped, so across both map lists
    it produces discarded entries and no re-expansions; it is kept in the properties that do not
    depend on re-expansion happening, and left out of the ones that measure it. The three below
    reach 429, 5 and 42 maps of the 1,312 swept, so the floor of 1 the measuring test asserts is a
    real assertion rather than a formality: an estimate that stopped re-expanding would fail.
    """

REOPENING_MAPS = sweep(
    ("3x3-two-foods-400-of-2592", sample(exhaustive(3, 3, frozenset(), 2), 400, seed=601)),
    (
        "3x4-walled-400-of-4050",
        sample(exhaustive(3, 4, frozenset({(1, 0), (1, 1)}), 2), 400, seed=602),
    ),
    ("random-4x4-dense", random_maps(50, 603, ((4, 4),), 0.3)),
    ("random-5x4-dense", random_maps(30, 604, ((5, 4),), 0.25, maxfoods=4)),
)
"""880 maps, the wall-heavy ones included, because that is where reopening bites.

    Each map costs four engine runs under the adversarial estimates plus one under the shipped
    one, so the two large families are fixed-seed samples of 400 rather than the whole 2,592 and
    4,050.
    """

DEFAULT_ESTIMATE_MAPS = sweep(
    *(
        (
            f"{size[0]}x{size[1]}-{int(density * 100)}pc-seed{seed}",
            random_maps(
                6,
                seed=seed * 977 + int(density * 100) + size[1],
                sizes=(size,),
                density=density,
                maxfoods=5,
            ),
        )
        for size in ((6, 6), (7, 6), (8, 6))
        for density in (0.15, 0.25, 0.35)
        for seed in (1, 8, 9, 14, 21, 22, 25, 28)
    ),
)
"""432 larger maps on which the shipped estimate really does re-expand states.

    Reopening under ``manhattan_mst`` is rare on the small maps above - it needs enough states for
    a state to be improved after being expanded - so this sweep is larger and denser: drawn from
    eight fixed seeds chosen because they produce re-expansions, at 15% to 35% obstacle density
    and up to five foods. 432 maps reaching 86,682 states, of which a dozen or so re-expand. The
    test asserts that at least one does, so the sweep cannot quietly stop covering the case it
    exists for.
    """

SHIPPED_REOPENING_MAP = OracleScenario(
    grid=OracleGrid(5, 5, frozenset({(0, 2), (0, 4), (1, 3)})),
    start=(3, 0),
    goal=(0, 0),
    foods=frozenset({(1, 4), (2, 0), (4, 2)}),
)
"""The pinned map on which ``manhattan_mst`` itself reopens a state."""


def _as_state(cell: tuple[int, int], collected: frozenset) -> SearchState:
    """Cross an oracle state over to the production ``SearchState``."""
    return SearchState(Position(*cell), frozenset(Position(*member) for member in collected))


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


def test_the_default_estimate_is_optimal_even_where_it_reopens_a_state() -> None:
    """A* under the shipped estimate is optimal on every map of the sweep, reopened or not.

    The default estimate is admissible but not consistent, so it reopens states on some maps.
    Where it does, the reopened state must not be able to make the run report a worse answer than
    a reference that never reopens anything. The sweep reaches about 100,000 expansions across
    both map sets, and the assertion at the end requires that at least one map re-expanded, so a
    sweep that quietly stopped covering the case would fail rather than pass vacuously.
    """
    problems = Discrepancies()
    reopened_maps = 0
    states_checked = 0
    for oracle_scenario in DEFAULT_ESTIMATE_MAPS + REOPENING_MAPS:
        scenario = to_scenario(oracle_scenario)
        runner = SearchRunner(scenario, heuristic=manhattan_mst)
        steps = []
        while (step := runner.step()) is not None:
            steps.append(step)
        result = runner.result()
        states_checked += len(steps)

        if len(steps) != len({step.state for step in steps}):
            reopened_maps += 1
        expected_found, expected_cost = held_karp(oracle_scenario)
        assert expected_found == ucs_mask(oracle_scenario)[0], describe(oracle_scenario)
        expected = (expected_found, expected_cost if expected_found else 0)
        if (result.found, result.cost) != expected:
            problems.add(
                oracle_scenario,
                f"astar reported (found={result.found}, cost={result.cost}), "
                f"the references say {expected}",
            )
        elif result.found:
            problem = _walk_problem(scenario, result.path)
            if problem is not None:
                problems.add(oracle_scenario, problem)

    problems.raise_if_any("the default estimate is optimal even where it reopens a state")
    assert states_checked > 30_000, f"only {states_checked} states were expanded"
    assert reopened_maps > 0, "no map in the sweep made the shipped estimate reopen a state"


def test_the_shipped_estimate_really_does_reopen_a_state_and_still_stays_optimal() -> None:
    """The default estimate is not merely documented to reopen: here is a map where it does.

    Five by five with three walls, three foods and a solvable layout::

        . . . . .
        . . . . F
        . # . . .
        S . . . .
        . F # . G

    ``(3, 2)`` is discovered at cost 3 and expanded, then reached again at cost 4 through
    ``(4, 2)`` and expanded a second time - so 75 expansions cover only 63 distinct states. The
    reopened run still reports the optimum, 15, which both references agree on.

    Without this, the reopening path of the engine would only ever be exercised by an inadmissible
    estimate, which is a weaker thing to pin.
    """
    scenario = to_scenario(SHIPPED_REOPENING_MAP)

    runner = SearchRunner(scenario, heuristic=manhattan_mst)
    steps = []
    while (step := runner.step()) is not None:
        steps.append(step)
    result = runner.result()

    assert len(steps) > len({step.state for step in steps}), (
        f"{describe(SHIPPED_REOPENING_MAP)} is meant to reopen a state"
    )
    assert result.found is True
    assert result.cost == 15, describe(SHIPPED_REOPENING_MAP)
    assert held_karp(SHIPPED_REOPENING_MAP)[1] == ucs_mask(SHIPPED_REOPENING_MAP)[1] == 15
    assert result == solve_bfs(scenario).success(result.path, result.expanded_states)
    assert _walk_problem(scenario, result.path) is None


@pytest.mark.parametrize("estimate", INCONSISTENT_ESTIMATES)
def test_the_rebuilt_path_is_always_a_real_walk_of_the_reported_length(
    estimate: Heuristic,
) -> None:
    """Under an estimate that reopens states, the parent chain still rebuilds a real walk.

    Parents are overwritten whenever a cost improves, so the chain finally walked back is not the
    chain discovered first. What must hold regardless is that every parent edge is one orthogonal
    move between walkable cells, that the walk starts at the start cell and ends on the goal, that
    it passes over every food, and that its length is exactly the reported cost.
    """
    problems = Discrepancies()
    for oracle_scenario in REOPENING_MAPS:
        scenario = to_scenario(oracle_scenario)

        runner = SearchRunner(scenario, heuristic=estimate)
        result = runner.run_to_completion()

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
            problems.add(oracle_scenario, f"a failed result is not empty: {result}")
        if result != runner.result():
            problems.add(oracle_scenario, "result() returned something other than the result")

    problems.raise_if_any("the rebuilt path is a real walk of the reported length")
    assert len(REOPENING_MAPS) == 880


@pytest.mark.parametrize("estimate", INCONSISTENT_ESTIMATES)
def test_the_rebuilt_walk_is_as_long_as_the_cost_the_run_recorded(estimate: Heuristic) -> None:
    """``len(path) - 1`` is the terminal state's recorded cost, not merely a self-consistent one.

    A stale parent chain could in principle rebuild a walk *shorter* than the cost the run
    recorded, which the result object cannot detect on its own because it only ever sees the path
    it was handed. This reaches into the run's own cost table to compare the two directly.

    The read of the private ``runner._best_cost`` below is deliberate and is the point of the test.
    It pins the joint-write invariant at ``runner.py:204-205``, where ``_expand`` writes
    ``_best_cost[successor]`` and ``_parents[successor]`` together as one unbreakable step: the
    cost table is updated exactly when the parent edge is rewritten, so the chain walked back from
    the terminal state is the chain that produced the recorded cost, and its length equals it. If
    either write were ever separated, or the parent edge were left worth more than one move, this
    is the assertion that would notice - and it cannot be written from outside the class, because
    no public accessor exposes a run's per-state cost.
    """
    problems = Discrepancies()
    for oracle_scenario in REOPENING_MAPS:
        scenario = to_scenario(oracle_scenario)

        runner = SearchRunner(scenario, heuristic=estimate)
        result = runner.run_to_completion()

        if not result.found:
            continue
        terminal = next(
            state
            for state in runner._best_cost
            if state.position == scenario.goal and state.collected == scenario.foods
        )
        recorded = runner._best_cost[terminal]
        if len(result.path) - 1 != recorded:
            problems.add(
                oracle_scenario,
                f"the walk is {len(result.path) - 1} moves but the run recorded cost {recorded}",
            )
        if result.cost != recorded:
            problems.add(
                oracle_scenario, f"result reports cost {result.cost}, the run recorded {recorded}"
            )

    problems.raise_if_any("the rebuilt walk is as long as the recorded cost")
    assert len(REOPENING_MAPS) == 880


@pytest.mark.parametrize("estimate", REOPENING_ESTIMATES)
def test_one_step_is_one_expansion_while_states_are_being_reopened(estimate: Heuristic) -> None:
    """Re-expansions are counted as expansions, one per step, on maps that reopen states.

    A superseded frontier entry is popped and dropped without producing a step; every step that is
    produced is one expansion, and the counts the steps report are 1, 2, 3, ... with no gap and
    no repeat. This is where stale-pop accounting would show up. Both map lists are swept, the
    larger ones included, because re-expansion under these estimates needs more states than a
    small map offers; the assertion that at least one map re-expanded is a real check on the
    estimate rather than a formality.
    """
    problems = Discrepancies()
    reopened_maps = 0
    for oracle_scenario in REOPENING_MAPS + DEFAULT_ESTIMATE_MAPS:
        scenario = to_scenario(oracle_scenario)
        runner = SearchRunner(scenario, heuristic=estimate)

        steps = []
        while (step := runner.step()) is not None:
            steps.append(step)

        counts = [step.statistics.expanded_states for step in steps]
        if counts != list(range(1, len(steps) + 1)):
            problems.add(oracle_scenario, f"expanded counts are not 1..n: {counts[:8]}")
        if runner.result().expanded_states != len(steps):
            problems.add(
                oracle_scenario,
                f"result reports {runner.result().expanded_states} expansions, "
                f"the stream showed {len(steps)}",
            )
        if len(steps) != len({step.state for step in steps}):
            reopened_maps += 1

    problems.raise_if_any("one step is one expansion while states are being reopened")
    assert reopened_maps > 0, (
        f"only {reopened_maps} maps re-expanded anything, so the estimate is not being exercised"
    )


@pytest.mark.parametrize("estimate", INCONSISTENT_ESTIMATES)
def test_an_unsolvable_map_terminates_under_an_inadmissible_estimate(estimate: Heuristic) -> None:
    """An exhausted run under a reopening estimate still terminates and reports the truth.

    The map has a food that cannot be reached, so there is no answer to be wrong about; what is
    checked is that the run ends, that the failure is an empty path and a zero cost, and that the
    counters do not claim fewer expansions than discoveries.
    """
    case = exhaustive(3, 2, frozenset({(1, 0), (1, 1)}), 1)[0]
    scenario = to_scenario(exhaustive(3, 2, frozenset({(1, 0), (1, 1)}), 1)[0])

    runner = SearchRunner(scenario, heuristic=estimate)
    steps = list(runner)
    result = runner.result()

    assert not result.found, describe(case)
    assert result.path == () and result.cost == 0
    assert result.expanded_states == len(steps)
    assert runner.statistics.frontier_size == 0
    assert runner.statistics.discovered_states <= runner.statistics.expanded_states


def test_an_admissible_estimate_can_report_more_expansions_than_discoveries_on_success() -> None:
    """A successful run may report ``expanded_states > discovered_states``, and that is fine.

    ``SearchStatistics.expanded_states`` documents the general form as
    ``expanded_states >= discovered_states - frontier_size``, and then says outright that a
    reopening search need not be as tidy as even that: it can find the optimal path while
    reporting *more* expanded states than discovered ones, because every reopening is an
    expansion with no matching discovery. This is the map that does it.

    The map below is 4x4 with four walls, start ``(3, 3)``, goal ``(0, 0)`` and three foods::

        G . # .
        . # # .
        F F # F
        . F F S

    The estimate is admissible on every reachable state of it, the run finds the optimum of 8 (which
    both references agree on), and it reports 44 expansions of 43 discovered states with three
    re-expansions. Pinned so that a future reader who wants to tighten the prose has to meet this
    case. What the prose *can* claim, and what this map confirms rather than contradicts, is the
    weaker bound written there: ``discovered_states - expanded_states <= frontier_size``.
    """
    oracle_scenario = OracleScenario(
        grid=OracleGrid(4, 4, frozenset({(1, 1), (2, 0), (2, 1), (2, 2)})),
        start=(3, 3),
        goal=(0, 0),
        foods=frozenset({(1, 2), (2, 3), (3, 2)}),
    )
    scenario = to_scenario(oracle_scenario)

    for state in reachable_states(oracle_scenario):
        remaining = true_remaining(oracle_scenario, *state)
        if remaining is not None:
            assert _goal_or_pending(scenario, _as_state(*state)) <= remaining, state

    runner = SearchRunner(scenario, heuristic=_goal_or_pending)
    steps = list(runner)
    result = runner.result()
    statistics = runner.statistics

    assert result.found is True
    assert result.cost == held_karp(oracle_scenario)[1] == ucs_mask(oracle_scenario)[1] == 8
    assert len(steps) - len({step.state for step in steps}) == 3, "this map is meant to reopen"
    assert statistics.expanded_states == 44
    assert statistics.discovered_states == 43
    assert statistics.expanded_states > statistics.discovered_states
    assert statistics.discovered_states - statistics.expanded_states <= statistics.frontier_size
    assert _walk_problem(scenario, result.path) is None
