"""The MST heuristic is checked as what it claims to be: a bound, not a guess.

The claim that matters is admissibility: the estimate never exceeds the true
remaining cost, and that is what makes A* return an optimal path here. The claim it
does *not* make - consistency - is pinned as broken rather than assumed, with the
smallest counterexample found, because an estimate that silently breaks a one-move
bound is exactly what a future reader must not re-derive a false proof about.

Neither test asks the search engine what the remaining cost is. The reference is a
breadth-first walk over the states written here, with its own queue and its own
distance map, so an error in the engine cannot cancel out an error in the estimate.

**Deliberate duplication.** ``test_heuristics_independent.py`` carries its own second copy of
these reachable-state and true-remaining-cost walks, over raw tuples. It has to: an independent
oracle must not share a helper with the suite it is checking, or one wrong assumption could
satisfy both sides at once.
"""

from collections import deque

import pytest
from conftest import build_scenario

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.heuristics import manhattan_mst, uniform_cost
from ant_pathfinding.search.state import SearchState

TERMINAL_CASES = [
    # . . .
    # . S .   the start is already the goal, nothing left to do
    pytest.param(
        build_scenario(3, 3, [], start=(1, 1), goal=(1, 1)),
        id="start-is-goal-without-food",
    ),
    # . . .
    # . S .   the only food is one step away, so the start state is not terminal
    # . F .
    pytest.param(
        build_scenario(3, 3, [], start=(1, 1), goal=(1, 1), foods=[(1, 2)]),
        id="start-is-goal-with-food-elsewhere",
    ),
    # . . .
    # . S .
    # F . G   the food is under the start, so it is already collected
    pytest.param(
        build_scenario(3, 3, [], start=(1, 1), goal=(2, 2), foods=[(1, 1)]),
        id="food-on-start",
    ),
    # . . .
    # . S .
    # . . G   the goal carries the only food, collected on arrival
    pytest.param(
        build_scenario(3, 3, [], start=(1, 1), goal=(2, 2), foods=[(2, 2)]),
        id="food-on-goal",
    ),
    # S
    pytest.param(
        build_scenario(1, 1, [], start=(0, 0), goal=(0, 0), foods=[(0, 0)]),
        id="start-is-goal-is-food",
    ),
]


def _reachable_states(scenario: AntScenario) -> set[SearchState]:
    """Every state the start can reach, found without the search engine."""
    start = SearchState(scenario.start, frozenset({scenario.start}).intersection(scenario.foods))
    seen = {start}
    queue: deque[SearchState] = deque((start,))
    while queue:
        state = queue.popleft()
        for neighbor in scenario.grid.neighbors(state.position):
            if not scenario.grid.is_walkable(neighbor):
                continue
            collected = (
                state.collected | {neighbor} if neighbor in scenario.foods else (state.collected)
            )
            successor = SearchState(neighbor, collected)
            if successor not in seen:
                seen.add(successor)
                queue.append(successor)
    return seen


def _true_remaining_cost(scenario: AntScenario, state: SearchState) -> int | None:
    """The exact number of moves still needed from ``state``, or ``None``.

    A plain breadth-first walk over the states from ``state`` onwards: collect what is
    still pending, then stand on the goal. Its own queue, its own distance map, no
    heuristic and no cost table shared with anything under test.
    """
    if state.position == scenario.goal and state.collected == scenario.foods:
        return 0
    distances = {state: 0}
    queue: deque[SearchState] = deque((state,))
    while queue:
        current = queue.popleft()
        depth = distances[current] + 1
        for neighbor in scenario.grid.neighbors(current.position):
            if not scenario.grid.is_walkable(neighbor):
                continue
            collected = (
                current.collected | {neighbor}
                if neighbor in scenario.foods
                else (current.collected)
            )
            successor = SearchState(neighbor, collected)
            if successor in distances:
                continue
            if successor.position == scenario.goal and successor.collected == scenario.foods:
                return depth
            distances[successor] = depth
            queue.append(successor)
    return None


def _solved_states(
    small_random_scenarios: list[AntScenario],
) -> list[tuple[AntScenario, SearchState]]:
    """Every reachable state of every solvable sampled scenario, with its scenario.

    A scenario with no solution is left out: the bound is only meaningful where a
    remaining cost exists at all. Nothing else has to be filtered, because once a
    scenario is solvable every state the start can reach is solvable from as well -
    walk the prefix that reached the state backwards, then follow a solution from the
    start, and the whole thing is a completion from that state.
    """
    solved: list[tuple[AntScenario, SearchState]] = []
    for scenario in small_random_scenarios:
        start = SearchState(
            scenario.start, frozenset({scenario.start}).intersection(scenario.foods)
        )
        if _true_remaining_cost(scenario, start) is None:
            continue
        for state in _ordered(_reachable_states(scenario)):
            solved.append((scenario, state))
    return solved


def _ordered(states: set[SearchState]) -> list[SearchState]:
    """Sort states into a fixed order, so a failure is reported the same way twice.

    ``SearchState`` has no ordering of its own - its collected set is a set - so the
    order is by cell and then by the collected cells.
    """
    return sorted(states, key=lambda state: (state.position, sorted(state.collected)))


def test_the_estimate_never_exceeds_the_true_remaining_cost(
    small_random_scenarios: list[AntScenario],
) -> None:
    """Admissibility: the estimate is at most the real cost, on every sampled state.

    This is the property the optimality of A* rests on. The remaining cost comes from
    a breadth-first walk written in this file, not from the search engine, so the two
    cannot be wrong together.
    """
    checked = 0
    tight = 0
    for scenario, state in _solved_states(small_random_scenarios):
        remaining = _true_remaining_cost(scenario, state)
        assert remaining is not None, scenario
        estimate = manhattan_mst(scenario, state)
        assert estimate <= remaining, (scenario, state, estimate, remaining)
        checked += 1
        tight += estimate == remaining
    assert checked >= 300
    # Walls, not the estimate, are what makes it loose, so it is usually exact.
    assert tight >= checked // 4


def test_the_estimate_is_neither_consistent_nor_one_sided() -> None:
    """The estimate breaks the one-move bound in both directions, and that is fine.

    Consistency would need ``h(s) <= 1 + h(s')`` across every move. It fails, because
    a move swaps the ant's own cell for a neighbouring one and the spanning tree is
    rebuilt around the newcomer, which may become a junction for the remaining targets.
    Here the vertex ``(0, 1)`` serves the food and the goal far better than ``(0, 2)``
    does::

        F # .
        . # .
        S . G

    Walking from ``(0, 2)`` up to ``(0, 1)`` drops the estimate from 5 to 3, two units
    for one move, and walking back raises it again. Neither ``h(s') <= 1 + h(s)`` nor
    its converse holds, so there is no one-sided bound to lean on either.

    What does hold is admissibility - the true remaining cost from ``(0, 2)`` is 7 -
    and admissibility plus a runner that reopens improved states is enough for
    optimality. This is pinned so the false proof is never re-derived: the fix is a
    reopened state, not a weaker estimate.
    """
    scenario = build_scenario(
        3, 3, [Position(1, 0), Position(1, 1)], start=(0, 2), goal=(2, 1), foods=[(0, 0)]
    )
    far = SearchState(Position(0, 2), frozenset())
    near = SearchState(Position(0, 1), frozenset())

    assert manhattan_mst(scenario, far) == 5
    assert manhattan_mst(scenario, near) == 3
    assert manhattan_mst(scenario, far) > 1 + manhattan_mst(scenario, near)
    assert manhattan_mst(scenario, near) < 1 + manhattan_mst(scenario, far)
    # Admissible all the same, on both sides of the move.
    assert _true_remaining_cost(scenario, far) == 7
    assert manhattan_mst(scenario, far) <= _true_remaining_cost(scenario, far)
    assert manhattan_mst(scenario, near) <= _true_remaining_cost(scenario, near)


@pytest.mark.parametrize("scenario", TERMINAL_CASES)
def test_the_estimate_is_zero_exactly_at_the_terminal_states(scenario: AntScenario) -> None:
    """``h == 0`` if and only if nothing is left: on the goal with every food.

    This is what the estimate relies on rather than assumes: food is collected on
    entry, so a state standing on a food cell has that food in ``collected`` and the
    pending set is empty exactly at the terminal states.
    """
    states = _ordered(_reachable_states(scenario))
    on_goal = [state for state in states if state.position == scenario.goal]
    assert on_goal, "the scenario must have a reachable goal"
    for state in states:
        is_terminal = state.position == scenario.goal and state.collected == scenario.foods
        assert (manhattan_mst(scenario, state) == 0) is is_terminal, (scenario, state)


def test_the_estimate_dominates_the_nearest_target_estimate(
    small_random_scenarios: list[AntScenario],
) -> None:
    """``h >= d(pos, t)`` for every remaining target, hence also the nearest one.

    ``max(d(pos, nearest food), d(pos, goal))`` is admissible and consistent too, and
    this shows it is dominated: it never grows with the number of remaining targets,
    so A* driven by it degenerates towards uniform-cost search.
    """
    checked = 0
    for scenario, state in _solved_states(small_random_scenarios):
        pending = frozenset(scenario.foods) - state.collected
        targets = pending | {scenario.goal}
        to_targets = max(_manhattan(state.position, target) for target in targets)
        estimate = manhattan_mst(scenario, state)
        assert estimate >= to_targets, (scenario, state, estimate, to_targets)
        to_goal = _manhattan(state.position, scenario.goal)
        assert estimate >= to_goal
        if pending:
            assert estimate >= min(_manhattan(state.position, food) for food in pending), (
                scenario,
                state,
            )
        checked += 1
    assert checked >= 300


def test_the_uniform_cost_estimate_is_zero_wherever_it_is_asked(
    small_random_scenarios: list[AntScenario],
) -> None:
    """The zero estimate ignores the scenario and the state, which is the point."""
    checked = 0
    for scenario, state in _solved_states(small_random_scenarios):
        assert uniform_cost(scenario, state) == 0
        checked += 1
    assert checked >= 300


def test_an_unreachable_scenario_is_left_to_the_search_not_to_the_estimate() -> None:
    """The estimate stays a finite number for an impossible problem.

    It has no way to know that a food is walled off, and it does not need to: with no
    completion walk the bound is true for any value. What matters is that it does not
    raise, and that A* still reports the failure.
    """
    scenario = build_scenario(
        3, 2, [Position(1, 0), Position(1, 1)], start=(0, 0), goal=(0, 1), foods=[(2, 1)]
    )
    start = SearchState(scenario.start, frozenset())

    assert manhattan_mst(scenario, start) == 1 + 1 + 1
    assert uniform_cost(scenario, start) == 0


def test_the_estimate_of_a_single_remaining_target_is_the_distance_to_it() -> None:
    """With one food left and the goal elsewhere the MST is the two legs of the route.

    For three vertices the MST is the cheaper of the two ways to join them, which is
    what makes the estimate grow with the number of remaining targets instead of
    staying at the distance to the closest one.
    """
    grid = Grid(width=9, height=1, blocked=frozenset())
    scenario = AntScenario(
        grid=grid, start=Position(0, 0), goal=Position(8, 0), foods=[Position(4, 0)]
    )
    collected = frozenset({Position(4, 0)})
    state = SearchState(Position(0, 0), collected)

    # Only the goal is left: a single leg.
    assert manhattan_mst(scenario, state) == 8
    # Food and goal both ahead of the ant: the legs join end to end.
    assert manhattan_mst(scenario, SearchState(Position(0, 0), frozenset())) == 8
    # Walking towards the food makes the estimate fall by exactly the move made.
    assert manhattan_mst(scenario, SearchState(Position(1, 0), frozenset())) == 7


def _manhattan(origin: Position, target: Position) -> int:
    return abs(origin.x - target.x) + abs(origin.y - target.y)
