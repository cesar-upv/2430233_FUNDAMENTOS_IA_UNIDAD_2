"""The progress contract: one test per documented property, each looping over the whole sweep.

A run is driven one expansion at a time here and everything the stream promises is read off it:
one step per expansion, a discovered state reported exactly once, the counters in a sane order,
and a result that does not depend on how the run was paced.

**Shape of this file.** One test per property, not one per property *and map*. Each test loops
over all three algorithms and every map of :data:`SWEEPS` internally and accumulates failures, so
the whole contract costs a dozen collected cases rather than a hundred and forty. The maps
matter: a run that reopens states is where a stale pop or a re-expansion mis-accounting would show
up, so wall-heavy maps and A* are included rather than skipped.

**Deliberate duplication.** ``test_progress.py`` carries its own copy of the step-driving
helper, of the uniform-cost frontier identity and of the maps used as fixtures, and
``conftest`` carries the shared scenario builders. This file does not import any of them: an
independent check of the progress contract must not be able to pass for the same reason as the
suite it is checking.
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
from independent_oracle import OracleGrid, OracleScenario, to_scenario

from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.algorithms import SearchAlgorithm, new_runner
from ant_pathfinding.search.astar import solve_astar
from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.dijkstra import solve_dijkstra
from ant_pathfinding.search.progress import SearchOutcome, SearchStatistics
from ant_pathfinding.search.state import SearchState

ALL_ALGORITHMS = [SearchAlgorithm.BFS, SearchAlgorithm.DIJKSTRA, SearchAlgorithm.ASTAR]
UNIFORM_COST = [SearchAlgorithm.BFS, SearchAlgorithm.DIJKSTRA]

SWEEPS = sweep(
    ("3x3-two-foods-400-of-2592", sample(exhaustive(3, 3, frozenset(), 2), 400, seed=501)),
    (
        "3x4-walled-400-of-4050",
        sample(exhaustive(3, 4, frozenset({(1, 0), (1, 1)}), 2), 400, seed=502),
    ),
    ("random-4x4-dense", random_maps(50, 503, ((4, 4),), 0.3)),
    ("random-5x4-dense", random_maps(30, 504, ((5, 4),), 0.25, maxfoods=4)),
    ("degenerate", [scenario for _, scenario in DEGENERATE_CASES]),
)
"""889 maps across six blocks; the scenarios are the data and a failure names the one.

    Every property below drives all three algorithms over this whole list, so each map costs
    about three dozen engine runs across the file. The map count is therefore kept modest and the
    two large families are fixed-seed samples: 889 maps, against 6,751 before consolidation and
    7,439 in the first version of this file. The coverage that matters is per property per
    algorithm, not per map: this file checks the contract, and the other four check the answers.
    """

WALLED_ORACLE = exhaustive(4, 3, frozenset({(1, 1), (2, 1)}), 2)[0]
"""A solvable map with two foods, a detour and more states than cells, used by the point tests.

    Kept as the raw oracle scenario as well as in its production form, because that is the
    only form ``describe`` can render: handing a ``Discrepancies`` collector an
    ``AntScenario`` makes the failure report raise instead of naming the map.
    """

WALLED = to_scenario(WALLED_ORACLE)
"""The same map, handed to the engine."""


def _start_state(scenario: AntScenario) -> SearchState:
    """The state a run begins in: the start cell, with any food under it already collected."""
    return SearchState(scenario.start, frozenset({scenario.start}) & scenario.foods)


def _drive(algorithm: SearchAlgorithm, scenario: AntScenario):
    """Step a fresh run to its end and return its steps, the runner and the result."""
    runner = new_runner(algorithm, scenario)
    steps = []
    while (step := runner.step()) is not None:
        steps.append(step)
    return steps, runner, runner.result()


def _over_every_map_and_algorithm(check) -> None:
    """Run ``check(oracle_scenario, algorithm, scenario)`` over the whole sweep.

    ``check`` returns a list of problem descriptions, empty when the property holds.
    """
    problems = Discrepancies()
    for oracle_scenario in SWEEPS:
        scenario = to_scenario(oracle_scenario)
        for algorithm in ALL_ALGORITHMS:
            found = check(oracle_scenario, algorithm, scenario)
            if isinstance(found, str):
                problems.add(oracle_scenario, f"{algorithm.value}: {found}")
            else:
                for problem in found:
                    problems.add(oracle_scenario, f"{algorithm.value}: {problem}")
    problems.raise_if_any("the progress contract holds over the sweep")
    assert len(SWEEPS) == 889


def test_one_step_is_exactly_one_expansion_and_the_run_reports_its_whole_life() -> None:
    """The expanded count rises by exactly one per step and ends at the result's count.

    A step that expanded nothing would repeat a count; a stale pop counted as an expansion would
    skip one. Neither shows up on an easy map, which is why the sweep includes walled grids and
    A*, the algorithm that reopens states.
    """

    def check(oracle_scenario, algorithm, scenario):
        steps, _runner, result = _drive(algorithm, scenario)
        counts = [step.statistics.expanded_states for step in steps]
        problems = []
        if not steps:
            problems.append("a run reported no steps at all")
        if counts != list(range(1, len(steps) + 1)):
            problems.append(f"expanded counts are not 1..n: {counts[:8]}")
        if result.expanded_states != len(steps):
            problems.append(
                f"result reports {result.expanded_states} expansions, "
                f"the stream showed {len(steps)}"
            )
        return problems

    _over_every_map_and_algorithm(check)


def test_the_last_step_already_reports_the_final_expansion_and_discovery_counts() -> None:
    """``expanded_states`` and ``discovered_states`` are already final on the last step.

    Both are taken after the expansion and its insertions, so nothing the run does after reporting
    can change them: an off-by-one would mean a step that reported the state before it was
    processed, or a run that counted a discovery it never reported.

    ``frontier_size`` is deliberately not in this list. The final ``step()`` may pop a superseded
    entry, discard it without producing a step, and then find the frontier empty - so a consumer
    that reads ``statistics`` after the last step can see a smaller frontier than the last step
    reported, with no step in between to explain it. That is consistent with the docstring, which
    says a superseded pop "is discarded without producing a step".
    """

    def check(oracle_scenario, algorithm, scenario):
        steps, runner, result = _drive(algorithm, scenario)
        last = steps[-1].statistics
        final = runner.statistics
        problems = []
        # Chained on purpose, and as equality: all three counts must agree, so a single
        # one of them being off by a step is enough to fail. Written as
        # ``a != b != c`` it would mean ``a != b and b != c`` and would pass whenever
        # the runner and the result drifted together.
        if not (last.expanded_states == final.expanded_states == result.expanded_states):
            problems.append(
                f"expanded: step {last.expanded_states}, runner {final.expanded_states}, "
                f"result {result.expanded_states}"
            )
        if last.discovered_states != final.discovered_states:
            problems.append(
                f"discovered: step {last.discovered_states}, runner {final.discovered_states}"
            )
        if last.frontier_peak_size != final.frontier_peak_size:
            problems.append("the peak frontier size changed after the last step")
        if final.frontier_size > last.frontier_size:
            problems.append("the frontier grew after the last step")
        return problems

    _over_every_map_and_algorithm(check)


def test_stepping_and_running_to_completion_are_the_same_run() -> None:
    """Full result equality, path included, between a stepped run and an unstepped one.

    Watching a run must change nothing about it, so a difference in the returned path would be a
    difference in the search and not in the pacing.
    """

    def check(oracle_scenario, algorithm, scenario):
        _steps, stepped, stepped_result = _drive(algorithm, scenario)
        direct = new_runner(algorithm, scenario).run_to_completion()
        problems = []
        if stepped_result != direct:
            problems.append(f"stepped {stepped_result} against direct {direct}")
        expected = SearchOutcome.FOUND if direct.found else SearchOutcome.EXHAUSTED
        if stepped.outcome is not expected:
            problems.append(f"outcome {stepped.outcome} against {expected}")
        return problems

    _over_every_map_and_algorithm(check)


def test_iterating_a_runner_reports_the_same_steps_as_calling_step() -> None:
    """The iterator is the same run, not a second opinion about it."""

    def check(oracle_scenario, algorithm, scenario):
        iterated = [step.state for step in new_runner(algorithm, scenario)]
        stepped = [step.state for step in _drive(algorithm, scenario)[0]]
        if iterated != stepped:
            return [f"iteration produced {len(iterated)} steps, step() {len(stepped)}"]
        return []

    _over_every_map_and_algorithm(check)


def test_each_state_is_reported_discovered_exactly_once() -> None:
    """A state is discovered in one step's ``discovered``, and the counts add up.

    The start state is the documented exception: it is inserted before the run is first stepped,
    so it appears in no step's ``discovered`` and every other state appears in exactly one.
    ``sum(len(step.discovered)) + 1 == discovered_states`` is the arithmetic that follows, and is
    asserted at the end of every run.
    """

    def check(oracle_scenario, algorithm, scenario):
        steps, runner, _result = _drive(algorithm, scenario)
        reported = [state for step in steps for state in step.discovered]
        problems = []
        if len(reported) != len(set(reported)):
            repeated = sorted({str(state) for state in reported if reported.count(state) > 1})
            problems.append(
                f"{len(reported) - len(set(reported))} states reported twice, e.g. {repeated[:2]}"
            )
        if _start_state(scenario) in set(reported):
            problems.append("the start state was reported as discovered")
        if steps[0].state != _start_state(scenario):
            problems.append("the first step did not expand the start state")
        if len(reported) + 1 != runner.statistics.discovered_states:
            problems.append(
                f"{len(reported)} reported plus the start is not "
                f"{runner.statistics.discovered_states} discovered"
            )
        return problems

    _over_every_map_and_algorithm(check)


def test_the_counters_never_invert_at_any_observation_point() -> None:
    """Discovered never falls below expanded, and the peak never below the current size.

    Checked at every step rather than only at the end, because that is what a consumer drawing a
    live frontier reads. A fresh runner also starts at exactly ``(0, 1, 1, 1)``: one state on the
    frontier, one discovered, nothing expanded.
    """

    def check(oracle_scenario, algorithm, scenario):
        runner = new_runner(algorithm, scenario)
        problems = []
        before = runner.statistics
        if before != SearchStatistics(0, 1, 1, 1):
            problems.append(f"a fresh runner reports {before}, expected (0, 1, 1, 1)")
        while True:
            statistics = runner.statistics
            if statistics.discovered_states < statistics.expanded_states:
                problems.append(f"discovered fell below expanded: {statistics}")
            if statistics.discovered_states < 1:
                problems.append(f"discovered below one: {statistics}")
            if statistics.frontier_peak_size < statistics.frontier_size:
                problems.append(f"peak below the current size: {statistics}")
            if statistics.frontier_peak_size < 1:
                problems.append(f"peak below one: {statistics}")
            if runner.step() is None:
                break
        if runner.statistics.expanded_states < 1:
            problems.append("a finished run expanded nothing")
        return problems

    _over_every_map_and_algorithm(check)


def test_a_uniform_cost_frontier_is_exactly_discovered_minus_expanded() -> None:
    """For the uniform-cost algorithms the frontier is exactly ``discovered - expanded``.

    Checked as a count identity and as a set identity over the states the stream reported, which
    is the promise a consumer is actually given. Only the two algorithms that never reopen a
    state can hold it, so only those two are checked.
    """
    problems = Discrepancies()
    for oracle_scenario in SWEEPS:
        scenario = to_scenario(oracle_scenario)
        for algorithm in UNIFORM_COST:
            steps, runner, _result = _drive(algorithm, scenario)
            statistics = runner.statistics
            discovered = {steps[0].state} | {s for step in steps for s in step.discovered}
            expanded = {step.state for step in steps}
            label = f"{algorithm.value}"
            if len(discovered) != statistics.discovered_states:
                problems.add(
                    oracle_scenario,
                    f"{label}: {len(discovered)} discovered states, counter says "
                    f"{statistics.discovered_states}",
                )
            if len(expanded) != statistics.expanded_states:
                problems.add(
                    oracle_scenario,
                    f"{label}: {len(expanded)} expanded states, counter says "
                    f"{statistics.expanded_states}",
                )
            if len(discovered - expanded) != statistics.frontier_size:
                problems.add(
                    oracle_scenario,
                    f"{label}: {len(discovered - expanded)} states are "
                    f"discovered-but-unexpanded, frontier_size is {statistics.frontier_size}",
                )
            if (
                statistics.discovered_states - statistics.expanded_states
                != statistics.frontier_size
            ):
                problems.add(oracle_scenario, f"{label}: the counter identity does not hold")

    problems.raise_if_any("the uniform-cost frontier is exactly discovered minus expanded")
    assert len(SWEEPS) == 889


def test_the_astar_frontier_identity_holds_as_an_inclusion_only() -> None:
    """A*'s frontier is at least ``discovered - expanded``, and may be larger.

    A reopened state sits on the frontier twice, so the weaker ``<=`` form holds where the exact
    identity holds for uniform cost. What must never happen is the other direction: a frontier
    smaller than the states discovered but not yet expanded, which would mean the counter and the
    stream disagree about what is queued.
    """
    problems = Discrepancies()
    for oracle_scenario in SWEEPS:
        scenario = to_scenario(oracle_scenario)
        steps, runner, _result = _drive(SearchAlgorithm.ASTAR, scenario)
        statistics = runner.statistics
        discovered = {steps[0].state} | {s for step in steps for s in step.discovered}
        expanded = {step.state for step in steps}
        if len(discovered) != statistics.discovered_states:
            problems.add(
                oracle_scenario,
                f"astar: {len(discovered)} discovered states, counter says "
                f"{statistics.discovered_states}",
            )
        if statistics.discovered_states - statistics.expanded_states > statistics.frontier_size:
            problems.add(
                oracle_scenario,
                f"astar: discovered minus expanded is "
                f"{statistics.discovered_states - statistics.expanded_states} but the "
                f"frontier holds {statistics.frontier_size}",
            )
        if len(discovered - expanded) > statistics.frontier_size:
            problems.add(
                oracle_scenario,
                f"astar: {len(discovered - expanded)} states are discovered-but-"
                f"unexpanded, frontier_size is {statistics.frontier_size}",
            )

    problems.raise_if_any("the A* frontier identity holds as an inclusion")
    assert len(SWEEPS) == 889


def test_an_exhausted_frontier_proves_that_nothing_was_left_to_try() -> None:
    """An exhausted run empties the frontier and expands at least every discovered state.

    Both together mean the run really did look everywhere, which is what makes the reported
    failure a proof rather than a guess. A reopening search may expand a state twice, so the count
    can exceed the discoveries; that is not a violation here.
    """

    def check(oracle_scenario, algorithm, scenario):
        runner = new_runner(algorithm, scenario)
        result = runner.run_to_completion()
        problems = []
        if runner.outcome is not SearchOutcome.EXHAUSTED:
            if result.found is not (runner.outcome is SearchOutcome.FOUND):
                problems.append(
                    f"outcome is {runner.outcome} but the result reports found={result.found}"
                )
            return problems
        # Reaching this point at all is the claim: only an exhausted run is checked for the
        # "nothing left to try" properties, and the outcome was compared above rather than
        # used as a precondition, so a result claiming success is a real failure here.
        if result.found:
            problems.append("outcome is EXHAUSTED but the result claims success")
        statistics = runner.statistics
        if statistics.frontier_size != 0:
            problems.append(
                f"outcome is EXHAUSTED but the frontier holds {statistics.frontier_size}"
            )
        if statistics.expanded_states < statistics.discovered_states:
            problems.append(
                f"exhausted with {statistics.discovered_states} discovered but only "
                f"{statistics.expanded_states} expanded"
            )
        if result.path or result.cost or result.expanded_states < 1:
            problems.append(f"a failed result is not empty: {result}")
        return problems

    _over_every_map_and_algorithm(check)


def test_a_failed_run_reports_no_path_and_no_cost_and_at_least_one_expansion() -> None:
    """A reported failure is an empty path, a zero cost and a real expansion count."""

    def check(oracle_scenario, algorithm, scenario):
        result = new_runner(algorithm, scenario).run_to_completion()
        if result.found:
            return []
        problems = []
        if result.path:
            problems.append(f"a failed result carries the path {result.path}")
        if result.cost:
            problems.append(f"a failed result carries cost {result.cost}")
        if result.expanded_states < 1:
            problems.append("a failed result claims zero expansions")
        return problems

    _over_every_map_and_algorithm(check)


def test_the_first_step_expands_the_start_state_with_the_start_already_queued() -> None:
    """Before the first step the frontier holds the start state and nothing has been expanded.

    This is the bookkeeping a consumer relies on to draw the very first frame: one state on the
    frontier, one discovered, zero expanded.
    """
    problems = Discrepancies()
    for algorithm in ALL_ALGORITHMS:
        runner = new_runner(algorithm, WALLED)
        before = runner.statistics

        step = runner.step()

        if before != SearchStatistics(0, 1, 1, 1):
            problems.add(WALLED_ORACLE, f"{algorithm.value}: a fresh runner reports {before}")
        if step is None:
            problems.add(WALLED_ORACLE, f"{algorithm.value}: the first step returned nothing")
            continue
        if step.state != _start_state(WALLED):
            problems.add(WALLED_ORACLE, f"{algorithm.value}: the first step expanded {step.state}")
        if step.statistics.expanded_states != 1:
            problems.add(
                WALLED_ORACLE,
                f"{algorithm.value}: the first step reports "
                f"{step.statistics.expanded_states} expansions",
            )

    problems.raise_if_any("the first step expands the start state")


def test_stopping_is_idempotent_and_never_overwrites_a_finished_run() -> None:
    """``stop()`` is safe before the first step, mid-run and after the end, any number of times.

    A finished ``FOUND`` or ``EXHAUSTED`` outcome is a fact about the scenario and is never
    overwritten; a stopped run keeps the statistics it reached, reports no result, and keeps
    reporting no result however often it is asked.
    """
    problems = Discrepancies()
    for algorithm in ALL_ALGORITHMS:
        label = f"{algorithm.value}"

        fresh = new_runner(algorithm, WALLED)
        fresh.step()
        for _ in range(3):
            fresh.stop()
        if fresh.outcome is not SearchOutcome.STOPPED:
            problems.add(WALLED_ORACLE, f"{label}: mid-run stop gives {fresh.outcome}")
        if fresh.finished is not True:
            problems.add(WALLED_ORACLE, f"{label}: a stopped run is not finished")
        if fresh.step() is not None:
            problems.add(WALLED_ORACLE, f"{label}: a stopped run still steps")
        for method in (fresh.result, fresh.run_to_completion):
            try:
                method()
            except RuntimeError as error:
                if "stopped" not in str(error):
                    problems.add(WALLED_ORACLE, f"{label}: {method.__name__} said {error}")
            else:
                problems.add(
                    WALLED_ORACLE, f"{label}: {method.__name__} returned instead of raising"
                )

        untouched = new_runner(algorithm, WALLED)
        untouched.stop()
        if untouched.outcome is not SearchOutcome.STOPPED:
            problems.add(
                WALLED, f"{label}: stopping before the first step gives {untouched.outcome}"
            )
        if untouched.step() is not None:
            problems.add(WALLED_ORACLE, f"{label}: a run stopped before its first step still steps")

        finished = new_runner(algorithm, WALLED)
        finished.run_to_completion()
        outcome, statistics = finished.outcome, finished.statistics
        for _ in range(3):
            finished.stop()
        if finished.outcome is not outcome:
            problems.add(
                WALLED_ORACLE,
                f"{label}: stopping a finished run changed {outcome} to {finished.outcome}",
            )
        if finished.statistics != statistics:
            problems.add(WALLED_ORACLE, f"{label}: stopping a finished run changed the statistics")
        if finished.step() is not None:
            problems.add(WALLED_ORACLE, f"{label}: a finished run still steps")

        stopped = new_runner(algorithm, WALLED)
        stopped.step()
        stopped.stop()
        if stopped.statistics.expanded_states < 1:
            problems.add(WALLED_ORACLE, f"{label}: stopping threw away the statistics reached")

    problems.raise_if_any("stop() is idempotent and never overwrites a finished run")


def test_a_result_is_only_available_once_the_run_is_over() -> None:
    """Asking early is an error, not an empty answer; asking after the end is fine."""
    problems = Discrepancies()
    for algorithm in ALL_ALGORITHMS:
        label = f"{algorithm.value}"
        runner = new_runner(algorithm, WALLED)
        try:
            runner.result()
        except RuntimeError as error:
            if "still running" not in str(error):
                problems.add(WALLED_ORACLE, f"{label}: said {error} before the first step")
        else:
            problems.add(WALLED_ORACLE, f"{label}: result() returned before the first step")

        while runner.step() is not None:
            if runner.outcome is not SearchOutcome.RUNNING:
                continue
            try:
                runner.result()
            except RuntimeError as error:
                if "still running" not in str(error):
                    problems.add(WALLED_ORACLE, f"{label}: said {error} mid-run")
            else:
                problems.add(WALLED_ORACLE, f"{label}: result() returned mid-run")

        try:
            runner.result()
        except RuntimeError as error:
            problems.add(WALLED_ORACLE, f"{label}: said {error} after the run ended")
    problems.raise_if_any("a result is only available once the run is over")


def test_two_runners_over_one_scenario_share_nothing() -> None:
    """Running or stopping one cannot advance, finish or disturb the other."""
    problems = Discrepancies()
    for algorithm in ALL_ALGORITHMS:
        label = f"{algorithm.value}"
        oracle_scenario = random_maps(1, 503, ((4, 3),), 0.2)[0]
        scenario = to_scenario(oracle_scenario)
        first = new_runner(algorithm, scenario)
        second = new_runner(algorithm, scenario)
        untouched = new_runner(algorithm, scenario)

        first.step()
        first.step()
        first.stop()
        if second.statistics != untouched.statistics:
            problems.add(oracle_scenario, f"{label}: stepping one runner moved the other")
        if second.outcome is not SearchOutcome.RUNNING:
            problems.add(oracle_scenario, f"{label}: the second runner is {second.outcome}")

        second_result = second.run_to_completion()
        if first.outcome is not SearchOutcome.STOPPED:
            problems.add(
                oracle_scenario, f"{label}: running the second finished the first ({first.outcome})"
            )

        fresh = new_runner(algorithm, scenario).run_to_completion()
        if second_result != fresh:
            problems.add(oracle_scenario, f"{label}: the shared scenario gave different answers")

    problems.raise_if_any("two runners over one scenario share nothing")


def test_running_to_completion_twice_returns_the_same_result() -> None:
    """A finished run is a fact, not a computation to repeat."""
    problems = Discrepancies()
    for algorithm in ALL_ALGORITHMS:
        runner = new_runner(algorithm, WALLED)
        first = runner.run_to_completion()
        statistics = runner.statistics
        again = runner.run_to_completion()
        if again is not first:
            problems.add(WALLED_ORACLE, f"{algorithm.value}: a second call rebuilt the result")
        if again != first:
            problems.add(WALLED_ORACLE, f"{algorithm.value}: a second call changed the result")
        if runner.statistics != statistics:
            problems.add(WALLED_ORACLE, f"{algorithm.value}: a second call changed the statistics")
    problems.raise_if_any("running to completion twice returns the same result")


def test_the_three_entry_points_agree_on_found_and_cost() -> None:
    """The three agree on the pair the optimality claim is about, and BFS on the whole result.

    A* is free to break ties between equal-length walks differently, so its path is not compared;
    the pair ``(found, cost)`` is.
    """
    problems = Discrepancies()
    for oracle_scenario in SWEEPS:
        scenario = to_scenario(oracle_scenario)
        breadth_first = solve_bfs(scenario)
        uniform_cost = solve_dijkstra(scenario)
        astar = solve_astar(scenario)
        if uniform_cost != breadth_first:
            problems.add(oracle_scenario, f"dijkstra {uniform_cost} against bfs {breadth_first}")
        if (astar.found, astar.cost) != (breadth_first.found, breadth_first.cost):
            problems.add(
                oracle_scenario,
                f"astar (found={astar.found}, cost={astar.cost}) against bfs "
                f"(found={breadth_first.found}, cost={breadth_first.cost})",
            )
    problems.raise_if_any("the three entry points agree on found and cost")


def test_the_uniform_cost_counter_identity_holds_at_every_observation_point() -> None:
    """``discovered_states == expanded_states + frontier_size`` after every single step.

    The docstring promises this identity at every observation point for a uniform-cost search,
    not only at the end, so it is checked on every step of every run of the sweep.
    """
    problems = Discrepancies()
    for oracle_scenario in SWEEPS:
        scenario = to_scenario(oracle_scenario)
        for algorithm in UNIFORM_COST:
            runner = new_runner(algorithm, scenario)
            while True:
                statistics = runner.statistics
                if statistics.discovered_states != (
                    statistics.expanded_states + statistics.frontier_size
                ):
                    problems.add(
                        oracle_scenario,
                        f"{algorithm.value}: {statistics} breaks the counter identity",
                    )
                    break
                if runner.step() is None:
                    break
    problems.raise_if_any("the uniform-cost counter identity holds at every observation point")
    assert len(SWEEPS) == 889


def test_a_successful_uniform_cost_run_expands_strictly_fewer_exactly_with_a_live_frontier() -> (
    None
):
    """A successful breadth-first run is short of its discoveries iff it returns with a frontier.

    This is the exact wording of ``solve_bfs``'s docstring, and it is a biconditional, so both
    directions are asserted: a non-empty frontier means fewer expansions than discoveries, and an
    empty frontier means the two counts are equal.
    """
    problems = Discrepancies()
    successful = 0
    for oracle_scenario in SWEEPS:
        runner = new_runner(SearchAlgorithm.BFS, to_scenario(oracle_scenario))
        result = runner.run_to_completion()
        if not result.found:
            continue
        successful += 1
        statistics = runner.statistics
        if statistics.frontier_size > 0:
            if statistics.expanded_states >= statistics.discovered_states:
                problems.add(
                    oracle_scenario,
                    f"a non-empty frontier but {statistics.expanded_states} expansions "
                    f"of {statistics.discovered_states} discoveries",
                )
        elif statistics.expanded_states != statistics.discovered_states:
            problems.add(
                oracle_scenario,
                f"an empty frontier but {statistics.expanded_states} expansions of "
                f"{statistics.discovered_states} discoveries",
            )
    problems.raise_if_any("a successful run expands strictly fewer exactly with a live frontier")
    assert successful > 500, f"only {successful} successful runs were checked"


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            OracleScenario(
                grid=OracleGrid(3, 3, frozenset()), start=(1, 1), goal=(1, 1), foods=frozenset()
            ),
            id="start-is-already-the-goal",
        ),
        pytest.param(
            OracleScenario(
                grid=OracleGrid(3, 1, frozenset()), start=(1, 0), goal=(0, 0), foods=frozenset()
            ),
            id="goal-is-the-starts-only-walkable-neighbour",
        ),
    ],
)
def test_both_named_examples_of_equal_counts_hold(case: OracleScenario) -> None:
    """The two cases ``solve_bfs`` names as having equal counts, named and checked.

    A successful run's two counts are equal when the goal state was the last state the run
    enqueued, "as when the start is already the goal or the goal is the start's only walkable
    neighbour". Both are the smallest maps where the terminal state is discovered immediately
    before it is expanded, so both leave nothing on the frontier.
    """
    runner = new_runner(SearchAlgorithm.BFS, to_scenario(case))
    result = runner.run_to_completion()
    statistics = runner.statistics

    assert result.found is True, describe(case)
    assert statistics.frontier_size == 0, describe(case)
    assert statistics.expanded_states == statistics.discovered_states, describe(case)


def test_neighbouring_steps_agree_about_the_counters_moving_forward() -> None:
    """Across the stream the discovered count never falls and the expanded count always rises by one.

    A cheap global check that the counters move forward monotonically and that the peak only
    grows, which is what a consumer reading a live frontier relies on.
    """
    steps, runner, _result = _drive(SearchAlgorithm.BFS, WALLED)
    initial = SearchStatistics(0, 1, 1, 1)
    problems = []
    for previous, current in pairwise([initial, *(step.statistics for step in steps)]):
        if current.discovered_states < previous.discovered_states:
            problems.append(f"discovered fell from {previous} to {current}")
        if current.expanded_states != previous.expanded_states + 1:
            problems.append(f"expanded jumped from {previous} to {current}")
        if current.frontier_peak_size < previous.frontier_peak_size:
            problems.append(f"the peak fell from {previous} to {current}")
    if runner.statistics.expanded_states != len(steps):
        problems.append(f"the runner expanded {runner.statistics.expanded_states} of {len(steps)}")
    assert not problems, problems
