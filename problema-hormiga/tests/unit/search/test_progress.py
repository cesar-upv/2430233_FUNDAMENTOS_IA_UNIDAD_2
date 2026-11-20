"""The observable progress contract: what a run reports, and when it stops reporting.

Stepping a runner one expansion at a time must be indistinguishable from letting it
run to completion - same path, same cost, same number of expansions - because that is
what makes an incremental run usable for anything that wants to watch one. The rest
of this file pins the four counters, the outcomes, and the promise the stream makes
to a consumer: a visualization needs nothing but the steps.

**Deliberate duplication.** ``test_progress_contract_independent.py`` carries its own
copy of the run-driving helper, of the walled scenario used as a fixture, and of the
uniform-cost frontier identity. It has to: an independent check that drove the runner
through a shared helper could not catch a defect in that helper, and a shared scenario
would let one broken map definition stand in for both suites.
"""

import pytest
from conftest import build_scenario

from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.algorithms import SearchAlgorithm, new_runner
from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.progress import SearchOutcome, SearchStatistics
from ant_pathfinding.search.result import SearchResult
from ant_pathfinding.search.runner import SearchRunner
from ant_pathfinding.search.state import SearchState

UNIFORM_COST = [SearchAlgorithm.BFS, SearchAlgorithm.DIJKSTRA]
ALL_ALGORITHMS = list(SearchAlgorithm)

WALLS = build_scenario(
    4, 3, [Position(1, 1), Position(2, 1)], start=(0, 0), goal=(3, 2), foods=[(0, 2), (3, 0)]
)
"""A solvable map with several foods, a detour and more states than cells."""


def _watched(algorithm: SearchAlgorithm, scenario: AntScenario) -> list[tuple[int, SearchState]]:
    """Expand a run one state at a time and report the count before each expansion."""
    runner = new_runner(algorithm, scenario)
    watched: list[tuple[int, SearchState]] = []
    while (step := runner.step()) is not None:
        watched.append((runner.statistics.expanded_states, step.state))
    return watched


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS, ids=[m.value for m in ALL_ALGORITHMS])
def test_stepping_one_at_a_time_equals_running_to_completion(
    algorithm: SearchAlgorithm, small_random_scenarios: list[AntScenario]
) -> None:
    """The answer does not depend on how the run was driven.

    Full equality, path included: the point of this test is that watching a run changes
    nothing about it, so any difference in the returned path would be a difference in
    the search, not in the pacing.
    """
    for scenario in [*small_random_scenarios[:8], WALLS]:
        stepped = new_runner(algorithm, scenario)
        while stepped.step() is not None:
            pass

        direct = new_runner(algorithm, scenario).run_to_completion()

        assert stepped.result() == direct, scenario
        assert stepped.outcome is (
            SearchOutcome.FOUND if direct.found else SearchOutcome.EXHAUSTED
        ), scenario


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS, ids=[m.value for m in ALL_ALGORITHMS])
def test_every_step_is_exactly_one_expansion(algorithm: SearchAlgorithm) -> None:
    """A step is one expansion, and the run's whole life is reported as steps.

    No step may report the same count as its predecessor - that would be a step that
    expanded nothing - and the last count is the count the result reports.
    """
    watched = _watched(algorithm, WALLS)

    assert len(watched) > 1
    assert [count for count, _ in watched] == list(range(1, len(watched) + 1))
    assert new_runner(algorithm, WALLS).run_to_completion().expanded_states == len(watched)


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS, ids=[m.value for m in ALL_ALGORITHMS])
def test_the_first_step_reports_the_start_state_already_queued(algorithm: SearchAlgorithm) -> None:
    """The first step expands the start state, and the frontier is never empty before it."""
    runner = new_runner(algorithm, WALLS)
    before = runner.statistics

    step = runner.step()

    assert step is not None
    assert step.state == SearchState(
        WALLS.start, frozenset({WALLS.start}).intersection(WALLS.foods)
    )
    assert step.statistics.expanded_states == 1
    assert before == SearchStatistics(0, 1, 1, 1)
    assert before.discovered_states >= before.expanded_states >= 0
    assert before.frontier_size >= 1
    assert before.frontier_peak_size >= 1


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS, ids=[m.value for m in ALL_ALGORITHMS])
def test_the_counters_never_invert(algorithm: SearchAlgorithm) -> None:
    """Discovered never falls below expanded, and the peak never below the current size.

    Checked at every observation point of a run, not only at its end, because that is
    what a consumer drawing a live frontier reads.
    """
    runner = new_runner(algorithm, WALLS)
    while True:
        statistics = runner.statistics
        assert statistics.discovered_states >= statistics.expanded_states >= 0
        assert statistics.frontier_peak_size >= statistics.frontier_size >= 0
        assert statistics.frontier_peak_size >= 1
        if runner.step() is None:
            break
    assert runner.statistics.expanded_states >= 1


def test_a_stopped_run_has_an_outcome_a_step_and_no_result() -> None:
    """Stopping ends the run honestly: an outcome, no steps, and no invented answer.

    A half-finished search knows no path, and reporting a failed result would claim the
    scenario has no solution - which is a different statement, and a wrong one here.
    """
    runner = new_runner(SearchAlgorithm.BFS, WALLS)
    runner.step()

    runner.stop()

    assert runner.outcome is SearchOutcome.STOPPED
    assert runner.finished is True
    assert runner.step() is None
    with pytest.raises(RuntimeError, match="stopped"):
        runner.result()
    with pytest.raises(RuntimeError, match="stopped"):
        runner.run_to_completion()


def test_stopping_is_idempotent_and_never_overwrites_a_finished_run() -> None:
    """Stop can be called at any point, any number of times, and cannot lie afterwards."""
    fresh = new_runner(SearchAlgorithm.BFS, WALLS)
    fresh.step()
    fresh.step()
    fresh.stop()
    fresh.stop()
    assert fresh.outcome is SearchOutcome.STOPPED
    assert fresh.step() is None

    for algorithm in ALL_ALGORITHMS:
        finished = new_runner(algorithm, WALLS)
        finished.run_to_completion()
        outcome = finished.outcome
        finished.stop()
        finished.stop()
        assert finished.outcome is outcome
        assert finished.step() is None
        assert finished.finished is True


def test_an_exhausted_frontier_proves_that_no_solution_exists() -> None:
    """Nothing left to expand means nothing left to try.

    ``. # .
    S # .
    # # G``

    The start and the cell above it are sealed off from the goal, so the run expands
    exactly the two states it discovered, the frontier runs empty and the run reports a
    failure - which for this map is a proof, not a guess.
    """
    walled_in = build_scenario(
        3,
        3,
        [Position(1, 0), Position(1, 1), Position(0, 2), Position(1, 2)],
        start=(0, 1),
        goal=(2, 2),
    )

    for algorithm in UNIFORM_COST:
        runner = new_runner(algorithm, walled_in)
        runner.run_to_completion()

        assert runner.outcome is SearchOutcome.EXHAUSTED
        assert runner.result().found is False
        assert runner.result().expanded_states == 2
        assert runner.statistics.frontier_size == 0
        assert runner.statistics.expanded_states == runner.statistics.discovered_states == 2


def test_a_result_is_only_available_once_the_run_is_over() -> None:
    """Asking early is an error, not an empty answer.

    The map has more states than one expansion clears, so the run is provably still live after
    the first step; that is asserted rather than assumed, because a conditional around the
    interesting assertion would let the test pass without ever making it.
    """
    runner = new_runner(SearchAlgorithm.BFS, WALLS)

    with pytest.raises(RuntimeError, match="still running"):
        runner.result()
    runner.step()
    assert runner.outcome is SearchOutcome.RUNNING
    with pytest.raises(RuntimeError, match="still running"):
        runner.result()

    runner.run_to_completion()
    assert runner.result().found is True


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS, ids=[m.value for m in ALL_ALGORITHMS])
def test_iterating_a_runner_reports_the_same_steps_as_calling_step(
    algorithm: SearchAlgorithm,
) -> None:
    """The iterator is the same run, not a second opinion about it."""
    iterated = [step.state for step in new_runner(algorithm, WALLS)]
    stepped = [state for _, state in _watched(algorithm, WALLS)]

    assert iterated == stepped


@pytest.mark.parametrize("algorithm", UNIFORM_COST, ids=[m.value for m in UNIFORM_COST])
def test_the_visualization_sets_can_be_derived_from_the_steps_alone(
    algorithm: SearchAlgorithm,
) -> None:
    """``discovered``, ``expanded`` and the frontier, all recovered from the stream.

    This is the promise a consumer is given: no accessor, no polling. Restricted to the
    uniform-cost algorithms, which never reopen a state, so that ``expanded`` is a set
    and the frontier is exactly ``discovered - expanded``.
    """
    runner = new_runner(algorithm, WALLS)

    steps = list(runner)
    discovered: set[SearchState] = set()
    expanded: set[SearchState] = set()
    for step in steps:
        discovered |= set(step.discovered)
        expanded.add(step.state)

    # The start state is the one state inserted before the first step, so the stream
    # never reports it as discovered; that single state is all a consumer has to add.
    discovered.add(steps[0].state)

    statistics = runner.statistics
    assert steps[0].state.position == WALLS.start
    assert expanded <= discovered
    assert len(discovered) == statistics.discovered_states
    assert len(expanded) == statistics.expanded_states
    assert len(discovered - expanded) == statistics.frontier_size
    assert statistics.frontier_peak_size >= statistics.frontier_size >= 0


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS, ids=[m.value for m in ALL_ALGORITHMS])
def test_running_to_completion_twice_returns_the_same_result(algorithm: SearchAlgorithm) -> None:
    """A finished run is a fact, not a computation to repeat."""
    runner = new_runner(algorithm, WALLS)

    first = runner.run_to_completion()
    statistics = runner.statistics

    assert runner.run_to_completion() is first
    assert runner.run_to_completion() == first
    assert runner.statistics == statistics


def test_a_superseded_frontier_entry_is_discarded_and_never_counted() -> None:
    """An entry the search already improved is popped and dropped, not expanded.

    The default estimate almost never re-improves a state, so this map is driven by an
    estimate that deliberately prefers the long way round - ``1000`` minus the distance
    from the start - which makes the runner order states by *detour*. A cell reached by
    a straight line then looks better than one reached cheaply, and the runner inserts a
    state, improves it before it is ever popped, and pops both entries::

        . . G .
        F . # .
        S . F .

    Here the run pops 37 entries for 36 expansions: the extra pop is the superseded one
    and the count below would be 37 if it were counted. Counting the pops is not part of
    the public contract, so what is asserted is what a consumer can see - one step per
    expansion, no state expanded twice on this map, and no superseded entry left over in
    the counters at the end.
    """
    scenario = build_scenario(
        4, 3, [Position(2, 1)], start=(0, 2), goal=(2, 0), foods=[(0, 1), (2, 2)]
    )

    def detour(problem: AntScenario, state: SearchState) -> int:
        return 1000 - (
            abs(state.position.x - problem.start.x) + abs(state.position.y - problem.start.y)
        )

    runner = SearchRunner(scenario, heuristic=detour)
    steps = [step.state for step in runner]

    assert len(steps) == len(set(steps)), "this map is meant to improve, not to re-expand"
    assert runner.result().expanded_states == len(steps)
    statistics = runner.statistics
    assert statistics.expanded_states == len(steps)
    assert statistics.discovered_states - statistics.expanded_states == statistics.frontier_size
    assert runner.result().cost == solve_bfs(scenario).cost


def test_an_improved_state_is_reopened_and_the_count_stays_truthful() -> None:
    """An inadmissible estimate may re-expand a state; the counters stay truthful.

    The default estimate is admissible and so hardly ever reopens anything, which would
    leave this path untested, so the run is driven by an estimate that is deliberately
    wrong. It rewards a state for having collected every food and is otherwise blind,
    which is inconsistent in the strongest way: a state first expanded at cost 9 is
    reached again at cost 7 and expanded a second time.

    The map is unsolvable, so the run exhausts everything and the counters can be read
    both ways round. Either way the estimate is the caller's responsibility - what must
    hold is that the run terminates and that its report is exact: one step per
    expansion, ``expanded_states`` counting expansions rather than distinct states, and
    an exhausted frontier.

        S # # . .
        . . . # G
        . # F F #
        . . F # .
    """
    scenario = build_scenario(
        5,
        4,
        [Position(x, y) for x, y in [(1, 0), (2, 0), (3, 1), (1, 2), (4, 2), (3, 3)]],
        start=(0, 0),
        goal=(4, 1),
        foods=[(2, 2), (3, 2), (2, 3)],
    )

    def greedy(problem: AntScenario, state: SearchState) -> int:
        return 0 if state.collected == problem.foods else 50

    runner = SearchRunner(scenario, heuristic=greedy)
    steps = [step.state for step in runner]

    assert runner.outcome is SearchOutcome.EXHAUSTED
    assert runner.result() == SearchResult.failure(len(steps))
    assert len(steps) > len(set(steps)), "this map is meant to re-expand a state"
    # Expanded counts expansions, not distinct states, and never counts a stale pop.
    assert runner.statistics.expanded_states == len(steps)
    assert runner.statistics.frontier_size == 0
    assert runner.statistics.discovered_states <= runner.statistics.expanded_states
    # The same map under a consistent estimate is expanded exactly once per state.
    uniform = new_runner(SearchAlgorithm.BFS, scenario)
    uniform.run_to_completion()
    assert uniform.result().expanded_states == uniform.statistics.discovered_states
