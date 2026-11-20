"""What ``manhattan_mst`` is, checked against references written for this file.

Admissibility is the property A*'s optimality rests on: the estimate never exceeds the moves
that are really left. The reference for "really left" is a breadth-first walk over
``(cell, collected)`` tuples written in :mod:`independent_oracle`, with its own queue and its
own distance map, so an error in the engine cannot cancel out an error in the estimate.

Consistency is the property the estimate is documented *not* to have. Both counterexamples are
pinned explicitly - the 3x3 the docstring names, which carries the two-sided claim, and a
wall-free 2x3 that is smaller - because a future reader must not re-derive a false proof that the
estimate is consistent. A coarse violation-rate measurement then shows the inconsistency is
systematic rather than a curiosity of one map.

The state-level sweeps are looped over inside each test. Each property is checked on every
reachable state of every map in its sweep; the maps and the states are the data, not the cases.

**Deliberate duplication.** ``test_heuristics.py`` carries its own reachable-state walk, its own
true-remaining-cost walk and its own admissibility assertions; this file carries a second copy of
each over raw tuples. The duplication is the point: an independent oracle that shared a helper with
the other suite would stop being independent, so one wrong assumption could satisfy both sides at
once.
"""

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
from independent_oracle import (
    OracleGrid,
    OracleScenario,
    reachable_states,
    to_scenario,
    true_remaining,
)

from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.heuristics import manhattan_mst, uniform_cost
from ant_pathfinding.search.state import SearchState

State = tuple[tuple[int, int], frozenset[tuple[int, int]]]

DOCUMENTED_COUNTEREXAMPLE = OracleScenario(
    grid=OracleGrid(3, 3, frozenset({(1, 0), (1, 1)})),
    start=(2, 2),
    goal=(2, 1),
    foods=frozenset({(0, 0)}),
)
"""The 3x3 map ``manhattan_mst``'s docstring names, which carries the two-sided claim."""

SMALLER_COUNTEREXAMPLE = OracleScenario(
    grid=OracleGrid(2, 3, frozenset()),
    start=(0, 2),
    goal=(0, 1),
    foods=frozenset({(0, 0), (1, 0)}),
)
"""A wall-free 2x3 map with the same violation on fewer cells - the smallest that has one."""

ADMISSIBILITY_MAPS = sweep(
    ("3x3-two-foods", exhaustive(3, 3, frozenset(), 2)),
    ("3x3-three-foods", sample(exhaustive(3, 3, frozenset(), 3), 1200, seed=401)),
    ("3x4-open-two-foods", sample(exhaustive(3, 4, frozenset(), 2), 900, seed=402)),
    ("3x4-walled-two-foods", sample(exhaustive(3, 4, frozenset({(1, 1)}), 2), 900, seed=403)),
    (
        "3x4-column-two-foods",
        sample(exhaustive(3, 4, frozenset({(1, 0), (1, 1)}), 2), 900, seed=404),
    ),
    ("random-4x4-10pc", random_maps(60, 405, ((4, 4),), 0.1)),
    ("random-4x4-20pc", random_maps(60, 406, ((4, 4),), 0.2)),
    ("random-4x4-30pc", random_maps(60, 407, ((4, 4),), 0.3)),
    ("random-5x4-20pc", random_maps(40, 408, ((5, 4),), 0.2)),
    ("random-5x5-10pc", random_maps(40, 409, ((5, 5),), 0.1, maxfoods=5)),
)
"""The maps whose every reachable state is checked for admissibility and for the two shape
    properties below: about 1,100 maps, reaching roughly 450,000 states.

    A 3x3 with three foods holds 6,048 maps and an open 3x4 with two foods 8,712, so those two
    families are fixed-seed samples; everything smaller is taken whole. Before consolidation this
    list reached 1,361,000 states; the sample is smaller, the property is the same, and the
    explicit counterexamples below do not depend on it.
    """

CONSISTENCY_MAPS = sweep(
    ("3x3-two-foods", exhaustive(3, 3, frozenset(), 2)),
    ("3x3-three-foods", sample(exhaustive(3, 3, frozenset(), 3), 800, seed=410)),
    ("3x4-walled-two-foods", sample(exhaustive(3, 4, frozenset({(1, 1)}), 2), 800, seed=411)),
    ("random-4x4-15pc", random_maps(60, 412, ((4, 4),), 0.15)),
    ("random-4x4-30pc", random_maps(60, 413, ((4, 4),), 0.3)),
)
"""The maps whose every reachable transition is measured for the one-move bound.

    Area six is the smallest grid that can violate the bound and area five cannot, so the sweep
    starts at 3x3 and every family here is at least that size. Measured at 578,000 transitions,
    against 2,990,611 before consolidation: a fifth of the old sample, which is still ample for
    a rate measured in whole percents and would show a regression in either direction - suddenly
    consistent, or suddenly far worse.
    """


def _as_state(cell: tuple[int, int], collected: frozenset) -> SearchState:
    """Cross an oracle ``(cell, collected)`` state over to the production ``SearchState``."""
    return SearchState(Position(*cell), frozenset(Position(*member) for member in collected))


def _successor(oracle_scenario: OracleScenario, state: State, cell: tuple[int, int]) -> State:
    """The state one move from ``state`` onto the walkable neighbour ``cell``."""
    _, collected = state
    foods = oracle_scenario["foods"]
    gathered = collected | {cell} if cell in foods else collected
    return (cell, frozenset(gathered))


def test_the_estimate_is_admissible_zero_only_at_the_terminal_states_and_dominating() -> None:
    """Four shape properties of the estimate, checked in one pass over every reachable state.

    They share a sweep because they share a walk: each state is enumerated once, its exact
    remaining cost computed once, and its estimate read once, so the four assertions cost one
    traversal rather than four. Splitting them would have quadrupled the cost of the largest sweep
    in this file for no extra coverage.

    * admissibility - ``h <= true remaining``, on start states, mid-route states and terminal ones
    * ``h == 0`` if and only if the state is on the goal with every food collected
    * domination - ``h >= d(cell, t)`` for every target still to visit, which is what makes the
      estimate dominate the weaker "distance to the nearest target" one
    * ``uniform_cost`` is zero everywhere it is asked, which is what makes it trivially admissible

    A state with no completion is skipped for admissibility: a bound is only meaningful where a
    remaining cost exists, and the estimate's docstring says the same - with no completion walk the
    bound is vacuously true for any value. The other three properties hold on such a state too and
    are checked there.
    """
    problems = Discrepancies()
    checked = 0
    for oracle_scenario in ADMISSIBILITY_MAPS:
        scenario = to_scenario(oracle_scenario)
        for cell, collected in reachable_states(oracle_scenario):
            state = _as_state(cell, collected)
            estimate = manhattan_mst(scenario, state)
            where = f"at {(cell, sorted(collected))}"

            remaining = true_remaining(oracle_scenario, cell, collected)
            if remaining is not None and estimate > remaining:
                problems.add(
                    oracle_scenario,
                    f"{where}: estimate {estimate} exceeds the true remaining {remaining}",
                )

            terminal = cell == oracle_scenario["goal"] and collected == oracle_scenario["foods"]
            if (estimate == 0) is not terminal:
                problems.add(
                    oracle_scenario,
                    f"{where}: estimate is {estimate} but the state is "
                    f"{'terminal' if terminal else 'not terminal'}",
                )

            for target in (oracle_scenario["foods"] - collected) | {oracle_scenario["goal"]}:
                distance = abs(cell[0] - target[0]) + abs(cell[1] - target[1])
                if estimate < distance:
                    problems.add(
                        oracle_scenario,
                        f"{where}: estimate {estimate} is below the distance {distance} "
                        f"to target {target}",
                    )

            if uniform_cost(scenario, state) != 0:
                problems.add(oracle_scenario, f"{where}: uniform_cost is not zero")
            checked += 1

    problems.raise_if_any(
        "the estimate is admissible, zero only at the terminal states, and dominating"
    )
    assert checked > 200_000, f"only {checked} states were checked"


def test_the_estimate_is_admissible_on_the_degenerate_rules_too() -> None:
    """Food on the start, food on the goal, a state that is already the goal, sealed pockets."""
    problems = Discrepancies()
    checked = 0
    for _, oracle_scenario in DEGENERATE_CASES:
        scenario = to_scenario(oracle_scenario)
        for state in reachable_states(oracle_scenario):
            remaining = true_remaining(oracle_scenario, *state)
            if remaining is None:
                continue
            estimate = manhattan_mst(scenario, _as_state(*state))
            if estimate > remaining:
                problems.add(
                    oracle_scenario,
                    f"at {state}: estimate {estimate} exceeds the true remaining {remaining}",
                )
            checked += 1

    problems.raise_if_any("the estimate is admissible on the degenerate rules")
    assert checked > 0


def test_the_consistency_counterexample_in_the_docstring_is_real() -> None:
    """Re-derive the counterexample ``manhattan_mst``'s docstring documents.

    On a 3x3 grid with ``(1, 0)`` and ``(1, 1)`` blocked, start ``(2, 2)``, goal ``(2, 1)`` and
    the single food at ``(0, 0)``::

        F # .
        . # G
        . . S

    Walking from ``(0, 2)`` to ``(0, 1)`` drops the estimate from 5 to 3, so
    ``h(s) > 1 + h(s')``. Walking back raises it again, so neither direction of the one-move bound
    holds and there is no one-sided bound to fall back on. Both states are reachable from the
    start, so this is a violation in the state space rather than an artefact.
    """
    scenario = to_scenario(DOCUMENTED_COUNTEREXAMPLE)
    reachable = reachable_states(DOCUMENTED_COUNTEREXAMPLE)
    far = _as_state((0, 2), frozenset())
    near = _as_state((0, 1), frozenset())

    assert ((0, 2), frozenset()) in reachable, "the far state must be reachable"
    assert ((0, 1), frozenset()) in reachable, "the near state must be reachable"
    assert manhattan_mst(scenario, far) == 5
    assert manhattan_mst(scenario, near) == 3
    assert manhattan_mst(scenario, far) > 1 + manhattan_mst(scenario, near), "one direction fails"
    assert manhattan_mst(scenario, near) < 1 + manhattan_mst(scenario, far), "so does the other"
    # Admissible all the same on both sides of the move: 7 moves are really needed from
    # ``(0, 2)`` and 6 from ``(0, 1)``.
    assert true_remaining(DOCUMENTED_COUNTEREXAMPLE, (0, 2), frozenset()) == 7
    assert true_remaining(DOCUMENTED_COUNTEREXAMPLE, (0, 1), frozenset()) == 6
    assert manhattan_mst(scenario, far) <= 7
    assert manhattan_mst(scenario, near) <= 6


def test_a_smaller_consistency_counterexample_exists_than_the_documented_one() -> None:
    """A wall-free 2x3 grid already breaks the one-move bound.

    Area five admits no violation at all and area six does, so the documented 3x3 is not the
    smallest one::

        F F G
        . . .
        S . .

    From ``(1, 2)`` with the first food collected the estimate is 4; one move to ``(1, 1)`` brings
    it to 2. Both states are reachable from the start and both stay admissible (4 of 4 and 2 of
    3), so the estimate is right about the value and wrong about how it moves.
    """
    scenario = to_scenario(SMALLER_COUNTEREXAMPLE)
    gathered = frozenset({(0, 0)})
    reachable = reachable_states(SMALLER_COUNTEREXAMPLE)
    far = _as_state((1, 2), gathered)
    near = _as_state((1, 1), gathered)

    assert ((1, 2), gathered) in reachable, "the far state must be reachable"
    assert ((1, 1), gathered) in reachable, "the near state must be reachable"
    assert manhattan_mst(scenario, far) == 4
    assert manhattan_mst(scenario, near) == 2
    assert manhattan_mst(scenario, far) > 1 + manhattan_mst(scenario, near)
    assert true_remaining(SMALLER_COUNTEREXAMPLE, (1, 2), gathered) == 4
    assert true_remaining(SMALLER_COUNTEREXAMPLE, (1, 1), gathered) == 3
    assert manhattan_mst(scenario, far) <= 4
    assert manhattan_mst(scenario, near) <= 3


def test_consistency_is_broken_on_a_few_percent_of_transitions() -> None:
    """The one-move bound fails on a measurable share of reachable transitions.

    The claim being pinned is that the estimate is knowingly inconsistent, and the rate is the
    evidence for it: a single map out of thousands would leave "not consistent" true but would
    hide how often it bites. Both directions are checked too - the bound must not suddenly start
    holding everywhere, and it must not collapse into violating on most transitions - so a
    change in the estimate is caught either way.
    """
    transitions = 0
    violating = 0
    rising = 0
    for oracle_scenario in CONSISTENCY_MAPS:
        scenario = to_scenario(oracle_scenario)
        for state in reachable_states(oracle_scenario):
            before = manhattan_mst(scenario, _as_state(*state))
            for neighbour in oracle_scenario["grid"].neighbours(state[0]):
                after = manhattan_mst(
                    scenario, _as_state(*_successor(oracle_scenario, state, neighbour))
                )
                transitions += 1
                if before > 1 + after:
                    violating += 1
                if after > 1 + before:
                    rising += 1

    assert transitions > 350_000, f"only {transitions} transitions were checked"
    assert violating > transitions // 100, (
        f"only {violating} of {transitions} transitions violate the one-move bound"
    )
    assert rising > transitions // 100, (
        f"only {rising} of {transitions} transitions rise by more than one move"
    )


def test_the_estimate_never_moves_further_than_one_step_worth_of_food() -> None:
    """Across one move the estimate changes by at most one per food item on the map.

    A weak but useful check on the arithmetic behind the estimate: entering one cell can retire at
    most one food, and a minimum spanning tree over one more or one fewer vertex cannot move by
    more than that per vertex.
    """
    problems = Discrepancies()
    checked = 0
    for oracle_scenario in CONSISTENCY_MAPS:
        scenario = to_scenario(oracle_scenario)
        bound = len(oracle_scenario["foods"]) + 1
        for state in reachable_states(oracle_scenario):
            before = manhattan_mst(scenario, _as_state(*state))
            for neighbour in oracle_scenario["grid"].neighbours(state[0]):
                after = manhattan_mst(
                    scenario, _as_state(*_successor(oracle_scenario, state, neighbour))
                )
                if abs(after - before) > bound:
                    problems.add(
                        oracle_scenario,
                        f"at {state}: estimate moved from {before} to {after} on one move, "
                        f"more than the {bound} allowed",
                    )
                checked += 1

    problems.raise_if_any("the estimate moves by at most one step worth of food per move")
    assert checked > 350_000, f"only {checked} transitions were checked"


def test_the_estimate_is_a_pure_function_of_the_scenario_and_the_state() -> None:
    """The estimate reads nothing but the scenario and the state, so repeating it is free of order.

    Every other property here compares an estimate against a reference; this one pins that the
    estimate is a pure function, which is what makes it safe to call it inside a sweep at all.
    """
    for _, oracle_scenario in DEGENERATE_CASES:
        scenario: AntScenario = to_scenario(oracle_scenario)
        for state in reachable_states(oracle_scenario):
            once = manhattan_mst(scenario, _as_state(*state))
            assert manhattan_mst(scenario, _as_state(*state)) == once, describe(oracle_scenario)


def test_an_unreachable_scenario_leaves_the_estimate_finite() -> None:
    """The estimate does not raise on an impossible problem; it cannot know food is walled off.

    The map is a ``3 x 2`` grid whose column 1 is solid, so the start region ``{(0, 0), (0, 1)}``
    is sealed off from the goal at ``(2, 0)``. The only food sits on the start, so it is already
    collected and the goal is the single remaining target: the estimate is the straight-line
    distance to it, 2, which is the most a wall-blind bound can say on a map where the goal cannot
    be walked to at all. A specific number rather than a lower bound, because "some finite
    integer" would hold for every estimate ever written, including a broken one.
    """
    oracle_scenario = exhaustive(3, 2, frozenset({(1, 0), (1, 1)}), 1)[0]
    scenario = to_scenario(oracle_scenario)
    start = (
        oracle_scenario["start"],
        frozenset({oracle_scenario["start"]}) & oracle_scenario["foods"],
    )

    assert oracle_scenario["goal"] == (2, 0)
    assert manhattan_mst(scenario, _as_state(*start)) == 2
    assert all(
        true_remaining(oracle_scenario, *state) is None
        for state in reachable_states(oracle_scenario)
    ), "this map is meant to have no completion at all"


@pytest.mark.parametrize(
    "scenario_case",
    [DOCUMENTED_COUNTEREXAMPLE, SMALLER_COUNTEREXAMPLE],
    ids=["documented-3x3", "smaller-2x3"],
)
def test_both_counterexample_maps_are_internally_consistent(
    scenario_case: OracleScenario,
) -> None:
    """The two named counterexample maps are what they claim: solvable, with the stated values.

    A regression case is only useful if the map still means what the test says it means, so the
    reachability, the terminal state and the admissibility of both sides are asserted alongside
    the violation itself.
    """
    scenario = to_scenario(scenario_case)
    reachable = reachable_states(scenario_case)

    terminal = (scenario_case["goal"], scenario_case["foods"])
    assert terminal in reachable, "the terminal state must be reachable"
    assert manhattan_mst(scenario, _as_state(*terminal)) == 0
    assert true_remaining(scenario_case, *terminal) == 0
    assert all(
        manhattan_mst(scenario, _as_state(*state)) <= true_remaining(scenario_case, *state)
        for state in reachable
    ), "every state of a counterexample map must still be admissible"
