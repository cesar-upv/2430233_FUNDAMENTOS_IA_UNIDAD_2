"""Adversarial verification of the multi-goal breadth-first search.

Maps are drawn with columns as ``x`` (left to right) and rows as ``y`` (top to
bottom): ``S`` is the start, ``G`` the goal, ``F`` food and ``#`` a blocked cell.

**What is checked here is behaviour, not the optimum.** Cost optimality is
cross-checked against independent references in
:mod:`tests.unit.search.test_optimality_independent`, which answers the same
question over far more maps with two references that share no code with the
engine. What stays here is what that suite has no equivalent for: the named
rules of the problem, the goal policy, the food and unreachability rules, and
expansion counts counted by hand on maps small enough to count them on. Every
expected cost below is therefore either hand-derived in the docstring of its
test or derived from the grid itself, never from a search.

The two references that remain are narrow and self-contained:

* :func:`_greedy_nearest_food_cost` reproduces the forbidden strategy - walk to
  the nearest uncollected food until none is left, then to the goal - so the
  tests can show it loses against the optimum. It carries its own flood fill
  because it is the only thing in this file that needs grid distances.
* :func:`_depth_limited_search` answers only "is there a walk of at most N
  moves", by depth-first descent that prunes a successor when the same state was
  already reached at a smaller depth. It shares no queue, no cost table and no
  monotone-cost reasoning with anything else here, so it can referee the engine's
  own reported cost: a walk of exactly that length must exist and no shorter one
  may.

**Deliberate duplication.** This file keeps its own scenario builder and its own
small hand-derived map tables instead of importing ``conftest``, and it asks for
the shared ``assert_valid_solution`` fixture only because that fixture reads
nothing from the engine. The maps drawn here and the maps drawn in the project
tests overlap on purpose: an independent check that reuses the code under test
proves nothing.

Random maps are generated from fixed seeds, and a map is always built so that at
least the start cell is walkable, which keeps every generated scenario valid.
"""

import random
from collections import deque
from collections.abc import Callable, Collection

import pytest

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.result import SearchResult
from ant_pathfinding.search.state import SearchState

UNREACHABLE = 1 << 30


# --------------------------------------------------------------------------
# The forbidden greedy strategy, reproduced as a counterexample
# --------------------------------------------------------------------------


def _greedy_nearest_food_cost(scenario: AntScenario) -> int | None:
    """Cost of the forbidden strategy: nearest food first, goal last.

    ``None`` when no food and no goal can be walked to at all from where the
    strategy stands. The flood fill is nested rather than shared, because this is
    the only reference left in the file that needs grid distances: nothing else
    here computes an optimum, so nothing else has a reason to.
    """

    def distances_from(source: Position) -> dict[Position, int]:
        distances: dict[Position, int] = {source: 0}
        queue: deque[Position] = deque((source,))
        while queue:
            current = queue.popleft()
            for neighbor in scenario.grid.neighbors(current):
                if not scenario.grid.is_walkable(neighbor) or neighbor in distances:
                    continue
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
        return distances

    position = scenario.start
    collected = {scenario.start} & set(scenario.foods)
    remaining = set(scenario.foods) - collected
    total = 0
    while remaining:
        reachable = distances_from(position)
        candidates = sorted(food for food in remaining if food in reachable)
        if not candidates:
            return None
        target = min(candidates, key=lambda food: (reachable[food], food))
        total += reachable[target]
        position = target
        remaining.discard(target)
    to_goal = distances_from(position)
    if scenario.goal not in to_goal:
        return None
    return total + to_goal[scenario.goal]


# --------------------------------------------------------------------------
# Map builders
# --------------------------------------------------------------------------


def _scenario(
    width: int,
    height: int,
    blocked: Collection[Position],
    start: tuple[int, int],
    goal: tuple[int, int],
    foods: Collection[tuple[int, int]] = (),
) -> AntScenario:
    return AntScenario(
        grid=Grid(width=width, height=height, blocked=frozenset(blocked)),
        start=Position(*start),
        goal=Position(*goal),
        foods=frozenset(Position(*cell) for cell in foods),
    )


def _random_scenario(seed: int, max_side: int, block_ratio: float, max_foods: int) -> AntScenario:
    """Build a valid scenario deterministically from ``seed``.

    ``Position(0, 0)`` is never blocked so that a scenario can always be built.
    """
    generator = random.Random(seed)
    width = generator.randint(1, max_side)
    height = generator.randint(1, max_side)
    cells = [Position(x, y) for y in range(height) for x in range(width)]
    blocked = {cell for cell in cells if generator.random() < block_ratio}
    blocked.discard(Position(0, 0))
    grid = Grid(width=width, height=height, blocked=blocked)
    free = [cell for cell in cells if grid.is_walkable(cell)]
    start = Position(0, 0)
    spare = [cell for cell in free if cell != start]
    goal = generator.choice(spare) if spare else start
    pool = [cell for cell in spare if cell != goal]
    generator.shuffle(pool)
    foods = frozenset(pool[: generator.randint(0, max_foods)])
    return AntScenario(grid=grid, start=start, goal=goal, foods=foods)


def _scenario_with_exactly(
    generator: random.Random, max_side: int, block_ratio: float, food_count: int
) -> AntScenario:
    """A valid scenario carrying exactly ``food_count`` foods where possible."""
    width = generator.randint(1, max_side)
    height = generator.randint(1, max_side)
    cells = [Position(x, y) for y in range(height) for x in range(width)]
    blocked = {cell for cell in cells if generator.random() < block_ratio}
    blocked.discard(Position(0, 0))
    grid = Grid(width=width, height=height, blocked=blocked)
    free = [cell for cell in cells if grid.is_walkable(cell)]
    start = Position(0, 0)
    spare = [cell for cell in free if cell != start]
    goal = generator.choice(spare) if spare else start
    pool = [cell for cell in spare if cell != goal]
    chosen = generator.sample(pool, min(food_count, len(pool)))
    return AntScenario(grid=grid, start=start, goal=goal, foods=frozenset(chosen))


# --------------------------------------------------------------------------
# Goal policy
# --------------------------------------------------------------------------


def test_goal_reached_with_food_outstanding_does_not_end_the_search(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """``. . . .
    # # . # #
    # # G # #
    F . . . .

    ``(2, 2)`` is the only doorway between the start row and the food row, so the
    optimum walks onto the goal after 4 steps, leaves again, and only finishes
    once the food at ``(0, 3)`` is collected.
    """
    blocked = [
        Position(0, 1),
        Position(1, 1),
        Position(3, 1),
        Position(4, 1),
        Position(0, 2),
        Position(1, 2),
        Position(3, 2),
        Position(4, 2),
    ]
    scenario = _scenario(5, 4, blocked, start=(0, 0), goal=(2, 2), foods=[(0, 3)])

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 10
    goal_visits = [index for index, cell in enumerate(result.path) if cell == scenario.goal]
    assert goal_visits == [4, len(result.path) - 1]
    assert Position(0, 3) in result.path
    # Standing on the goal four steps in is strictly cheaper than the answer, so
    # the run demonstrably did not stop there. Four is the walking distance of
    # ``(0, 0) -> (1, 0) -> (2, 0) -> (2, 1) -> (2, 2)``, which the very same grid
    # answers with the food removed.
    without_food = AntScenario(
        grid=scenario.grid, start=scenario.start, goal=scenario.goal, foods=frozenset()
    )
    blind = solve_bfs(without_food)
    assert blind.found is True
    assert blind.cost == 4
    assert result.cost > blind.cost


def test_goal_that_is_a_one_cell_bridge_is_crossed_twice(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """``S G .
    # # .
    . . F

    The goal is the only cell that links the start to the food, so it is entered
    at step 1 and again at the end.
    """
    scenario = _scenario(
        3, 3, [Position(0, 1), Position(1, 1)], start=(0, 0), goal=(1, 0), foods=[(2, 2)]
    )

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 7
    assert result.path[1] == scenario.goal
    assert result.path[-1] == scenario.goal
    assert result.path.count(scenario.goal) == 2


def test_start_on_the_goal_costs_zero_without_food(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    scenario = _scenario(4, 4, [], start=(2, 2), goal=(2, 2))

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.path == (scenario.start,)
    assert result.cost == 0
    assert result.expanded_states == 1


def test_start_on_the_goal_leaves_and_returns_to_collect_food(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """Both corners are two steps away and the two trips cannot share a leg."""
    scenario = _scenario(3, 3, [], start=(1, 1), goal=(1, 1), foods=[(0, 0), (2, 2)])

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 8
    assert result.path[0] == result.path[-1] == scenario.goal


def test_single_cell_grid_solves_at_cost_zero(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    scenario = _scenario(1, 1, [], start=(0, 0), goal=(0, 0))

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 0
    assert result.expanded_states == 1


# --------------------------------------------------------------------------
# Food handling
# --------------------------------------------------------------------------


def test_food_under_the_start_needs_no_return_trip(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """The straight walk already collects it, so it costs nothing at all."""
    scenario = _scenario(5, 1, [], start=(0, 0), goal=(4, 0), foods=[(0, 0)])

    result = solve_bfs(scenario)
    without_food = AntScenario(
        grid=scenario.grid, start=scenario.start, goal=scenario.goal, foods=frozenset()
    )

    assert_valid_solution(scenario, result)
    assert result.cost == 4
    assert solve_bfs(without_food).cost == 4


def test_food_under_the_start_and_one_elsewhere_is_collected_on_arrival(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """The route walks through the goal before the far food is collected."""
    scenario = _scenario(3, 3, [], start=(0, 0), goal=(2, 0), foods=[(0, 0), (2, 2)])

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 6
    assert result.path.index(scenario.goal) == 2
    assert result.path.index(Position(2, 2)) == 4


def test_food_on_the_goal_is_collected_on_arrival(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """The goal carries the only food, so arriving is the same as finishing."""
    scenario = _scenario(3, 3, [], start=(0, 0), goal=(2, 2), foods=[(2, 2)])

    result = solve_bfs(scenario)
    without_food = AntScenario(
        grid=scenario.grid, start=scenario.start, goal=scenario.goal, foods=frozenset()
    )

    assert_valid_solution(scenario, result)
    assert result.cost == 4
    assert solve_bfs(without_food).cost == 4


def test_repeated_food_positions_behave_like_a_single_item() -> None:
    once = _scenario(5, 1, [], start=(0, 0), goal=(4, 0), foods=[(2, 0)])
    thrice = _scenario(5, 1, [], start=(0, 0), goal=(4, 0), foods=[(2, 0), (2, 0), (2, 0)])

    assert thrice.foods == once.foods
    assert solve_bfs(thrice) == solve_bfs(once)


def test_food_list_is_not_consulted_after_the_call() -> None:
    foods = [Position(2, 0)]
    scenario = AntScenario(
        grid=Grid(width=5, height=1, blocked=frozenset()),
        start=Position(0, 0),
        goal=Position(4, 0),
        foods=foods,
    )

    first = solve_bfs(scenario)
    foods.append(Position(3, 0))

    assert solve_bfs(scenario) == first


# --------------------------------------------------------------------------
# Unreachable food and unreachable goals
# --------------------------------------------------------------------------


def test_food_in_a_fully_enclosed_pocket_has_no_solution() -> None:
    """``(1, 1)`` is walled on all four sides while start and goal stay linked."""
    scenario = _scenario(
        4,
        4,
        [Position(1, 0), Position(0, 1), Position(2, 1), Position(1, 2)],
        start=(3, 3),
        goal=(3, 0),
        foods=[(1, 1)],
    )

    result = solve_bfs(scenario)

    # Column 3 is open top to bottom, so the goal is reachable in three moves and the
    # failure below is caused by the food alone.
    assert all(scenario.grid.is_walkable(Position(3, y)) for y in range(4))
    # 16 cells, 4 blocked, so 12 walkable - of which ``(0, 0)`` is walled in by
    # ``(1, 0)`` and ``(0, 1)`` and ``(1, 1)`` by its four neighbours. That leaves ten
    # reachable states, and an exhausted run expands exactly all of them.
    assert result.found is False
    assert result.path == ()
    assert result.cost == 0
    assert result.expanded_states == 10


def test_food_behind_a_single_wall_column_has_no_solution() -> None:
    """Column 1 is solid, so the right-hand pocket is never entered."""
    scenario = _scenario(
        3, 2, [Position(1, 0), Position(1, 1)], start=(0, 0), goal=(0, 1), foods=[(2, 0)]
    )

    result = solve_bfs(scenario)

    assert result.found is False
    assert result.path == ()
    assert result.cost == 0
    assert result.expanded_states == 2


def test_reachable_food_does_not_rescue_an_unreachable_goal() -> None:
    """Row 0 is open, so the food is one step away - and the goal is sealed off."""
    scenario = _scenario(
        3, 3, [Position(1, 2), Position(2, 1)], start=(0, 0), goal=(2, 2), foods=[(2, 0)]
    )

    result = solve_bfs(scenario)

    assert all(scenario.grid.is_walkable(Position(x, 0)) for x in range(3))
    assert result.found is False
    assert result.path == ()
    assert result.cost == 0


def test_reachable_goal_does_not_rescue_an_unreachable_food() -> None:
    scenario = _scenario(
        4,
        4,
        [Position(1, 0), Position(0, 1), Position(2, 1), Position(1, 2)],
        start=(3, 3),
        goal=(0, 0),
        foods=[(1, 1)],
    )

    result = solve_bfs(scenario)

    assert result.found is False
    assert result.path == ()
    assert result.cost == 0


def test_goal_sealed_in_a_corner_reports_a_failure() -> None:
    """``G # . . .
    # . . . .
    . . . . .
    . . . . .
    . . . . .

    The goal is walled off by ``(1, 0)`` and ``(0, 1)``; the other 22 cells are
    walkable and all reachable, so the run exhausts them and fails.
    """
    scenario = _scenario(5, 5, [Position(1, 0), Position(0, 1)], start=(4, 4), goal=(0, 0))

    result = solve_bfs(scenario)

    assert result.found is False
    assert result.path == ()
    assert result.cost == 0
    assert result.expanded_states == 22


def test_start_sealed_in_a_corner_expands_only_the_start_state() -> None:
    """``. . .
    # # .
    S . .

    The start has no walkable neighbour, so the run ends after one expansion.
    """
    scenario = _scenario(3, 3, [Position(1, 0), Position(0, 1)], start=(0, 0), goal=(2, 2))

    result = solve_bfs(scenario)

    assert result.found is False
    assert result.expanded_states == 1


def test_start_on_the_goal_with_unreachable_food_reports_a_failure() -> None:
    scenario = _scenario(
        4,
        3,
        [Position(1, 0), Position(1, 1), Position(1, 2)],
        start=(0, 1),
        goal=(0, 1),
        foods=[(3, 1)],
    )

    result = solve_bfs(scenario)

    assert result.found is False
    assert result.path == ()
    assert result.expanded_states == 3


def test_a_single_unreachable_food_turns_a_solvable_scenario_into_a_failure() -> None:
    """The same grid solves without the extra food and fails with it.

    ``S . G
    # # .
    F # .

    The food at ``(0, 2)`` has no walkable neighbour, while the goal stays
    reachable in four moves along the top row and down the right column.
    """
    grid = Grid(
        width=3, height=3, blocked=frozenset({Position(0, 1), Position(1, 1), Position(1, 2)})
    )
    without = AntScenario(grid=grid, start=Position(0, 0), goal=Position(2, 2), foods=frozenset())
    with_food = AntScenario(
        grid=grid,
        start=Position(0, 0),
        goal=Position(2, 2),
        foods=frozenset({Position(0, 2)}),
    )

    assert all(grid.is_walkable(Position(x, 0)) for x in range(3))
    assert solve_bfs(without).cost == 4
    assert solve_bfs(with_food).found is False
    assert solve_bfs(with_food).path == ()
    assert solve_bfs(with_food).cost == 0
    assert solve_bfs(with_food).expanded_states >= 1


# --------------------------------------------------------------------------
# The state must carry the collected food
# --------------------------------------------------------------------------


def test_visited_cells_alone_cannot_solve_this_map(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """``F # F
    . S .
    . G .

    ``(1, 0)`` is blocked, so both sides of the start are walked twice and the
    start cell itself is entered three times, each time carrying a different
    collected set. The optimum is 9: down to ``(0, 1)``, across to ``(2, 1)``, up
    to the food, back to the food, and down through the start to the goal.
    """
    scenario = _scenario(3, 3, [Position(1, 0)], start=(1, 1), goal=(1, 2), foods=[(0, 0), (2, 0)])

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 9
    assert result.path.count(scenario.start) == 3
    assert result.path.count(Position(0, 1)) == 2
    assert len(set(result.path)) < len(result.path)


def test_the_same_cell_is_entered_with_different_collected_food() -> None:
    scenario = _scenario(3, 3, [Position(1, 0)], start=(1, 1), goal=(1, 2), foods=[(0, 0), (2, 0)])

    visited: dict[Position, list[frozenset[Position]]] = {}
    collected: frozenset[Position] = frozenset()
    for cell in solve_bfs(scenario).path:
        if cell in scenario.foods:
            collected |= {cell}
        visited.setdefault(cell, []).append(collected)

    assert len(visited[scenario.start]) == 3
    assert len(set(visited[scenario.start])) == 3


def test_a_food_blind_search_would_stop_too_early_on_every_detour_map() -> None:
    """Dropping the food from a scenario can never make the answer more expensive.

    A search that only remembers visited cells answers exactly this weaker
    problem, so on every map where collecting food forces a detour the
    food-blind answer is strictly cheaper - which is why a food-blind search
    stops early on all of them.
    """
    generator = random.Random(4242)
    checked = 0
    compared = 0
    for _ in range(200):
        scenario = _random_scenario(
            seed=generator.randint(0, 10_000), max_side=6, block_ratio=0.3, max_foods=3
        )
        if not scenario.foods:
            continue
        blind_scenario = AntScenario(
            grid=scenario.grid,
            start=scenario.start,
            goal=scenario.goal,
            foods=frozenset(),
        )
        blind = solve_bfs(blind_scenario)
        result = solve_bfs(scenario)
        if not blind.found or not result.found:
            continue
        assert blind.cost <= result.cost, scenario
        checked += blind.cost < result.cost
        compared += 1
    assert compared >= 20, f"only {compared} solvable comparisons"
    assert checked >= 20, f"only {checked} of {compared} maps force a detour"


def test_collecting_nearest_food_first_is_not_optimal(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """``. . . . . . . . . . G
    . . . . . . . . . . .
    . . . . . . . . . . .
    . F . . . . . . . . .

    Column 0 below the start is a corridor. Food ``(1, 0)`` is one step away while
    food ``(0, 3)`` is three steps away, so nearest-first walks ``(0, 0) -> (0, 3)
    -> (0, 0) -> (1, 0) -> G`` for 18 steps, while the optimum is
    ``d(S, (0, 3)) + d((0, 3), (1, 0)) + d((1, 0), G) = 3 + 4 + 9 = 16``.
    """
    blocked = frozenset(Position(x, y) for y in (1, 2, 3) for x in range(11) if x != 0)
    scenario = _scenario(11, 4, blocked, start=(0, 0), goal=(10, 0), foods=[(1, 0), (0, 3)])

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.cost == 16
    greedy = _greedy_nearest_food_cost(scenario)
    assert greedy == 18
    assert greedy is not None
    assert result.cost < greedy
    assert result.path.index(Position(0, 3)) < result.path.index(Position(1, 0))


def test_the_search_is_never_worse_than_the_forbidden_greedy_strategy() -> None:
    """Over random maps the optimal walk is at worst as long as the greedy one.

    The greedy strategy is only compared where it produces a walk at all: if it
    can finish, a solution exists, so the search must find one and cannot be
    longer. At least one map of the sweep has to be strictly better, so a sweep
    where the two stopped differing would fail rather than pass.
    """
    generator = random.Random(31_337)
    strictly_better = 0
    compared = 0
    for _ in range(60):
        scenario = _random_scenario(
            seed=generator.randint(0, 10_000), max_side=6, block_ratio=0.3, max_foods=3
        )
        if not scenario.foods:
            continue
        greedy = _greedy_nearest_food_cost(scenario)
        if greedy is None:
            continue
        result = solve_bfs(scenario)
        assert result.found is True, scenario
        assert result.cost <= greedy, scenario
        compared += 1
        strictly_better += result.cost < greedy
    assert compared >= 20, f"only {compared} maps were compared"
    assert strictly_better >= 1, "the greedy strategy was never beaten"


# --------------------------------------------------------------------------
# Expanded-state accounting, counted by hand
# --------------------------------------------------------------------------


def test_two_by_two_counts_two_expansions_and_three_discoveries() -> None:
    """``expanded_states`` counts queue removals, not discovered states.

    The start is popped and expanded (1), both of its walkable neighbours are
    discovered, and the goal neighbour is popped and expanded (2) before
    ``(0, 1)`` is ever popped. The run returns there with ``(0, 1)`` still
    waiting in the frontier, so on this 2x2 grid 3 states are discovered and 2
    expanded: the expanded count falls short of the discovered count by exactly
    the states left queued.
    """
    scenario = _scenario(2, 2, [], start=(0, 0), goal=(1, 0))
    grid = scenario.grid
    discovered = 1 + sum(1 for cell in grid.neighbors(scenario.start) if grid.is_walkable(cell))

    result = solve_bfs(scenario)

    assert result.cost == 1
    assert result.expanded_states == 2
    assert discovered == 3
    assert result.expanded_states < discovered


def test_expansions_are_hand_countable_on_a_one_row_grid() -> None:
    scenario = _scenario(3, 1, [], start=(0, 0), goal=(2, 0))

    result = solve_bfs(scenario)

    assert (result.found, result.cost, result.expanded_states) == (True, 2, 3)


def test_a_food_in_the_middle_of_a_line_does_not_add_expansions() -> None:
    scenario = _scenario(3, 1, [], start=(0, 0), goal=(2, 0), foods=[(1, 0)])

    result = solve_bfs(scenario)

    assert (result.found, result.cost, result.expanded_states) == (True, 2, 3)


def test_food_on_the_goal_still_needs_every_cell_of_the_line_expanded() -> None:
    """On a 5 x 1 line with food on the goal, all five cells are expanded.

    The reachable state space is larger than the five expanded states - four cells
    carrying nothing collected, and five carrying the food - but the run never
    leaves the goal behind it, so it stops after the fifth pop.
    """
    scenario = _scenario(5, 1, [], start=(0, 0), goal=(4, 0), foods=[(4, 0)])

    result = solve_bfs(scenario)

    assert (result.found, result.cost, result.expanded_states) == (True, 4, 5)


@pytest.mark.parametrize(
    "name, width, height, blocked, start, goal, foods, expected",
    [
        ("single cell", 1, 1, [], (0, 0), (0, 0), [], (True, 0, 1)),
        ("two cell line", 2, 1, [], (0, 0), (1, 0), [], (True, 1, 2)),
        ("two by two goal east", 2, 2, [], (0, 0), (1, 0), [], (True, 1, 2)),
        ("food in the middle of a line", 3, 1, [], (0, 0), (2, 0), [(1, 0)], (True, 2, 3)),
        ("two by two, food beside the start", 2, 2, [], (0, 0), (1, 1), [(0, 1)], (True, 2, 5)),
        ("two by two, food on the goal", 2, 2, [], (0, 0), (1, 1), [(1, 1)], (True, 2, 4)),
        ("line, goal in the middle", 5, 1, [], (0, 0), (2, 0), [(4, 0)], (True, 6, 7)),
        ("line, goal second, food last", 4, 1, [], (0, 0), (1, 0), [(3, 0)], (True, 5, 6)),
    ],
)
def test_expansion_counts_that_can_be_counted_by_hand(
    name: str,
    width: int,
    height: int,
    blocked: Collection[Position],
    start: tuple[int, int],
    goal: tuple[int, int],
    foods: Collection[tuple[int, int]],
    expected: tuple[bool, int, int],
) -> None:
    scenario = _scenario(width, height, blocked, start=start, goal=goal, foods=foods)

    result = solve_bfs(scenario)

    assert (result.found, result.cost, result.expanded_states) == expected, name


@pytest.mark.parametrize("length", range(2, 13))
def test_on_a_line_the_number_of_expansions_is_the_number_of_cells(length: int) -> None:
    """A line graph is walked in order, so the last cell popped is the goal."""
    scenario = _scenario(length, 1, [], start=(0, 0), goal=(length - 1, 0))

    result = solve_bfs(scenario)

    assert result.cost == length - 1
    assert result.expanded_states == length


def test_a_successful_search_expands_at_least_the_states_of_its_own_path() -> None:
    """Every state along the returned path was popped before the run stopped."""
    generator = random.Random(7_777)
    checked = 0
    for _ in range(120):
        scenario = _random_scenario(
            seed=generator.randint(0, 10_000), max_side=6, block_ratio=0.3, max_foods=4
        )
        result = solve_bfs(scenario)
        if not result.found:
            continue
        assert result.expanded_states >= result.cost + 1
        checked += 1
    assert checked >= 40


def test_the_start_cell_is_a_second_state_once_it_carries_food(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """``1 x 6`` line, food at ``(1, 0)`` and ``(4, 0)``, goal at ``(5, 0)``.

    Walking the line collects both foods in five steps, so the answer is the
    straight walk. The state space is larger than that - one state with nothing
    collected, four carrying ``(1, 0)`` only and six carrying both - but only the
    straight walk is ever popped, plus the start cell re-entered from ``(1, 0)``
    carrying food. Counting pops by hand gives seven expansions.
    """
    scenario = _scenario(6, 1, [], start=(0, 0), goal=(5, 0), foods=[(1, 0), (4, 0)])

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.path == tuple(Position(x, 0) for x in range(6))
    assert result.cost == 5
    assert result.expanded_states == 7


def test_a_start_with_no_walkable_neighbour_expands_only_its_own_state() -> None:
    """Every cell is walled off except the start and the far-away goal."""
    width = height = 4
    open_cells = {Position(0, 0), Position(3, 3)}
    blocked = [
        Position(x, y)
        for y in range(height)
        for x in range(width)
        if Position(x, y) not in open_cells
    ]
    scenario = _scenario(width, height, blocked, start=(0, 0), goal=(3, 3), foods=[(3, 3)])

    result = solve_bfs(scenario)

    assert result.found is False
    assert result.path == ()
    assert result.cost == 0
    assert result.expanded_states == 1


def test_expanded_states_counts_dequeued_states_and_leaves_the_frontier_on_success() -> None:
    """Discovered states are the expanded ones plus whatever is still queued.

    ``solve_bfs`` documents exactly that. A failed run exhausts the queue, so
    ``expanded_states`` equals the number of discovered states. A successful run
    stops as soon as the terminal goal state leaves the queue, so the expanded
    count is at most the discovered count: it is equal when the run returns with
    an empty frontier - the goal state was the last state the run enqueued - and
    smaller only when it returns with a non-empty one.

    The failed map is a ``3 x 3`` grid whose goal corner is sealed off::

        S # G
        . . #
        . . .

    Seven of the nine cells are walkable, the goal ``(2, 0)`` is walled in by
    ``(1, 0)`` and ``(2, 1)``, and the other six are one connected region. The
    queue is exhausted, so the count is those six reachable states.

    The successful map is a ``3 x 2`` grid whose start has exactly two walkable
    neighbours, the goal among them::

        S G #
        . . #

    The start is expanded first and enqueues both neighbours, so those three
    states are everything the run has discovered when it returns on the goal: two
    of them are expanded and the other is still waiting in the frontier, which is
    the non-empty-frontier branch. That count is derived from the grid, not from
    the search, so it cannot drift with the reported number. The empty-frontier
    branch is pinned by
    :func:`test_success_expands_every_discovered_state_when_the_frontier_is_empty_at_return`.
    """
    stuck = _scenario(3, 3, [Position(1, 0), Position(2, 1)], start=(0, 0), goal=(2, 0))
    grid = stuck.grid
    discovered_on_failure = (
        sum(1 for y in range(3) for x in range(3) if grid.is_walkable(Position(x, y))) - 1
    )

    stuck_result = solve_bfs(stuck)

    assert stuck_result.found is False
    assert stuck_result.path == ()
    assert stuck_result.cost == 0
    assert discovered_on_failure == 6
    assert stuck_result.expanded_states == discovered_on_failure

    solved = _scenario(3, 2, [Position(2, 1)], start=(0, 0), goal=(1, 0))
    solved_grid = solved.grid

    discovered_on_success = 1 + sum(
        1 for cell in solved_grid.neighbors(solved.start) if solved_grid.is_walkable(cell)
    )

    result = solve_bfs(solved)

    assert result.found is True
    assert result.cost == 1
    assert discovered_on_success == 3
    assert 1 <= result.expanded_states <= discovered_on_success
    assert result.expanded_states < discovered_on_success


def test_success_expands_every_discovered_state_when_the_frontier_is_empty_at_return() -> None:
    """A successful run expands the discovered states exactly when it leaves nothing queued.

    On an open ``3 x 3`` grid the start is already the goal and there is no food,
    so the run returns on the first pop without generating a single successor: it
    discovered one state and expanded it, and the rest of the state space is
    irrelevant because nothing beyond the start was ever enqueued::

        S . .
        . . .
        . . .

    On the second map the start has a single walkable neighbour, the goal::

        S G #
        # # .
        . . .

    The start is expanded and enqueues the goal, which is the last state the run
    enqueues, so two states are discovered and both are expanded.
    """
    already_goal = _scenario(3, 3, [], start=(0, 0), goal=(0, 0))

    immediate = solve_bfs(already_goal)

    assert immediate.found is True
    assert immediate.cost == 0
    assert immediate.path == (already_goal.start,)
    assert immediate.expanded_states == 1

    only_neighbour = _scenario(
        3, 3, [Position(0, 1), Position(1, 1), Position(2, 0)], start=(0, 0), goal=(1, 0)
    )
    grid = only_neighbour.grid
    discovered = 1 + sum(
        1 for cell in grid.neighbors(only_neighbour.start) if grid.is_walkable(cell)
    )

    result = solve_bfs(only_neighbour)

    assert discovered == 2
    assert result.found is True
    assert result.cost == 1
    assert result.path == (only_neighbour.start, only_neighbour.goal)
    assert result.expanded_states == discovered


def test_more_states_are_expanded_than_there_are_cells() -> None:
    """A position-only visited set would have fewer states than this.

    Each map below forces the ant back through a cell it has already left, so a
    search that merges "same cell" with "same cell and same collected food" can
    neither expand as many states nor return the cost asserted here. The cell
    counts and the costs are read off the grid and off a route that achieves the
    bound, not off the search.
    """
    maps = [
        # the start cell is reachable again carrying food, on a 1 x 6 line:
        # 6 cells, and the straight walk collects both foods in 5
        (_scenario(6, 1, [], start=(0, 0), goal=(5, 0), foods=[(1, 0), (4, 0)]), 6, 5),
        # (1, 1) is the only bridge over the wall and is walked in both directions:
        # 8 cells, and both corners plus the goal need 6 moves
        (
            _scenario(3, 3, [Position(1, 1)], start=(1, 0), goal=(1, 2), foods=[(0, 0), (2, 0)]),
            8,
            6,
        ),
        # the goal cell is the only doorway to the food and is crossed twice:
        # 7 cells, and the only route is out along row 0, round column 2 and back
        (
            _scenario(
                3,
                3,
                [Position(0, 1), Position(1, 1)],
                start=(0, 0),
                goal=(1, 0),
                foods=[(2, 2)],
            ),
            7,
            7,
        ),
        # a detour is unavoidable, so the far side is entered in several states:
        # 15 cells, and ``S -> (0, 3) -> (1, 1) -> (3, 0) -> G`` costs 3 + 3 + 3 + 3
        (
            _scenario(
                4, 4, [Position(2, 1)], start=(0, 0), goal=(3, 3), foods=[(0, 3), (3, 0), (1, 1)]
            ),
            15,
            12,
        ),
    ]
    for scenario, cells, cost in maps:
        result = solve_bfs(scenario)
        assert result.found is True, scenario
        assert result.cost == cost, (result.cost, cost)
        assert result.expanded_states > cells, (result.expanded_states, cells)


def test_a_cell_keeps_being_walkable_after_its_food_was_taken(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """A collected cell must stay walkable, or the route would close behind the ant.

    ``S G F
    # # .
    # # .

    The goal cell is the only doorway to the food, so it is walked twice. It also
    carries a food item, which the first visit collects and the second one finds
    already taken: without that the search could stop at step 1 with the far food
    still on the board. Three moves are forced: one to the goal, one to the food
    and one back.
    """
    scenario = _scenario(
        3,
        3,
        [Position(0, 1), Position(1, 1), Position(0, 2), Position(1, 2)],
        start=(0, 0),
        goal=(1, 0),
        foods=[(1, 0), (2, 0)],
    )

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.path == (
        Position(0, 0),
        Position(1, 0),
        Position(2, 0),
        Position(1, 0),
    )
    assert result.cost == 3
    assert result.path.count(scenario.goal) == 2


def test_a_food_in_a_dead_end_the_ant_must_enter_and_leave_again(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """``F # F
    S # .
    # # G
    """
    scenario = _scenario(
        3,
        3,
        [Position(1, 0), Position(2, 0), Position(0, 2), Position(1, 2)],
        start=(0, 1),
        goal=(2, 2),
        foods=[(0, 0)],
    )

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    assert result.path == (
        Position(0, 1),
        Position(0, 0),
        Position(0, 1),
        Position(1, 1),
        Position(2, 1),
        Position(2, 2),
    )
    assert result.cost == 5


def test_an_optimal_path_never_repeats_a_state() -> None:
    generator = random.Random(606)
    checked = 0
    for _ in range(60):
        scenario = _random_scenario(
            seed=generator.randint(0, 10_000), max_side=6, block_ratio=0.3, max_foods=3
        )
        result = solve_bfs(scenario)
        if not result.found:
            continue
        collected: frozenset[Position] = frozenset({scenario.start} & scenario.foods)
        states = [SearchState(scenario.start, collected)]
        for cell in result.path[1:]:
            collected = collected | {cell} if cell in scenario.foods else collected
            states.append(SearchState(cell, collected))
        assert len(set(states)) == len(states), "an optimal path cannot loop"
        checked += 1
    assert checked >= 20, f"only {checked} successful walks were checked"


# --------------------------------------------------------------------------
# Determinism and absence of hidden state
# --------------------------------------------------------------------------


def test_repeated_calls_return_equal_results() -> None:
    scenario = _scenario(
        6, 5, [Position(2, 2), Position(3, 1)], start=(0, 0), goal=(5, 4), foods=[(4, 0), (0, 4)]
    )

    first = solve_bfs(scenario)
    second = solve_bfs(scenario)

    assert first == second


def test_solving_does_not_mutate_the_scenario_or_its_grid() -> None:
    scenario = _scenario(
        5, 4, [Position(1, 1), Position(3, 3)], start=(0, 0), goal=(4, 3), foods=[(2, 2), (0, 3)]
    )
    blocked_before = scenario.grid.blocked
    foods_before = scenario.foods

    solve_bfs(scenario)

    assert scenario.grid.blocked == blocked_before
    assert scenario.foods == foods_before
    assert scenario.grid.is_walkable(Position(1, 1)) is False
    assert scenario.grid.is_walkable(Position(2, 2)) is True


def test_a_previously_solved_scenario_does_not_influence_the_next_one() -> None:
    """Two scenarios solved in both orders must give both their own answers."""
    first = _scenario(5, 1, [], start=(0, 0), goal=(4, 0), foods=[(1, 0)])
    second = _scenario(5, 1, [], start=(0, 0), goal=(4, 0), foods=[(3, 0)])

    forward = (solve_bfs(first).path, solve_bfs(second).path)
    backward = (solve_bfs(second).path, solve_bfs(first).path)

    assert forward == (backward[1], backward[0])


# --------------------------------------------------------------------------
# A reference: depth-limited search that only answers "within N moves"
# --------------------------------------------------------------------------


def _depth_limited_search(
    grid: Grid, start: Position, goal: Position, foods: frozenset[Position], limit: int
) -> bool:
    """Whether some legal walk of at most ``limit`` moves solves the problem.

    A depth-first descent that prunes a successor only when the identical state
    was already reached at a smaller depth inside this call. The pruning is what
    makes it terminate, and it is sound because a state reached later can only
    offer a longer continuation of anything the earlier visit could offer.
    """
    full = frozenset(foods)
    initial = SearchState(start, frozenset({start}) & foods)
    if initial.position == goal and initial.collected == full:
        return True
    shallowest: dict[SearchState, int] = {initial: 0}
    stack = [initial]
    while stack:
        state = stack.pop()
        depth = shallowest[state]
        if depth == limit:
            continue
        for neighbor in grid.neighbors(state.position):
            if not grid.is_walkable(neighbor):
                continue
            collected = state.collected | {neighbor} if neighbor in foods else state.collected
            successor = SearchState(neighbor, collected)
            if shallowest.get(successor, UNREACHABLE) <= depth + 1:
                continue
            if neighbor == goal and collected == full:
                return True
            shallowest[successor] = depth + 1
            stack.append(successor)
    return False


def _the_reported_cost_is_the_smallest_possible(scenario: AntScenario) -> None:
    """Referee the search's own answer: a walk of that length, and none shorter.

    The referee is given the cost the run reported rather than a cost from another
    reference, which is what makes it a referee: it says whether *that* number is
    minimal without consulting anything derived from the same search.
    """
    grid = scenario.grid
    result = solve_bfs(scenario)
    if not result.found:
        # No walk exists at all, so a generous move budget must come up empty.
        assert (
            _depth_limited_search(grid, scenario.start, scenario.goal, scenario.foods, 90) is False
        )
        return
    assert _depth_limited_search(grid, scenario.start, scenario.goal, scenario.foods, result.cost)
    if result.cost:
        assert (
            _depth_limited_search(
                grid, scenario.start, scenario.goal, scenario.foods, result.cost - 1
            )
            is False
        ), "a shorter walk exists, so the reported cost is not minimal"


@pytest.mark.parametrize("seed", range(60))
def test_a_depth_limited_search_confirms_the_optimum_on_small_maps(seed: int) -> None:
    _the_reported_cost_is_the_smallest_possible(
        _random_scenario(20_000 + seed, max_side=5, block_ratio=0.25, max_foods=3)
    )


@pytest.mark.parametrize("seed", range(40))
def test_a_depth_limited_search_confirms_the_optimum_on_roomy_maps(seed: int) -> None:
    """Long detours make ``cost - 1`` a meaningful negative result."""
    _the_reported_cost_is_the_smallest_possible(
        _random_scenario(21_000 + seed, max_side=7, block_ratio=0.3, max_foods=4)
    )


def test_no_walk_one_step_shorter_than_the_reported_cost_exists_on_many_maps() -> None:
    generator = random.Random(61_501)
    checked = 0
    for _ in range(120):
        scenario = _random_scenario(
            seed=generator.randint(0, 10_000), max_side=7, block_ratio=0.3, max_foods=4
        )
        result = solve_bfs(scenario)
        if not result.found or result.cost == 0:
            continue
        grid = scenario.grid
        assert _depth_limited_search(
            grid, scenario.start, scenario.goal, scenario.foods, result.cost
        )
        assert not _depth_limited_search(
            grid, scenario.start, scenario.goal, scenario.foods, result.cost - 1
        )
        checked += 1
    assert checked >= 30


# --------------------------------------------------------------------------
# Robustness sweep over shapes and food counts
# --------------------------------------------------------------------------


@pytest.mark.parametrize("side", [1, 2, 3, 4, 5, 6, 7, 8])
def test_every_shape_from_a_single_cell_to_an_eight_by_eight_solves_consistently(
    side: int,
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """Only invariants are asserted here; no expected cost comes from the search."""
    generator = random.Random(90_000 + side)
    solvable = 0
    for _ in range(12):
        scenario = _random_scenario(
            seed=generator.randint(0, 10_000), max_side=side, block_ratio=0.3, max_foods=3
        )
        result = solve_bfs(scenario)
        if result.found:
            assert_valid_solution(scenario, result)
            solvable += 1
        else:
            assert result.path == ()
            assert result.cost == 0
            assert result.expanded_states >= 1
    assert solvable >= 3


@pytest.mark.parametrize("food_count", [0, 1, 2, 3, 4, 5, 6])
def test_more_food_never_makes_the_optimum_cheaper(food_count: int) -> None:
    """A walk that collects everything is also a walk that collects less."""
    generator = random.Random(13_000 + food_count)
    compared = 0
    for _ in range(15):
        scenario = _scenario_with_exactly(
            generator, max_side=6, block_ratio=0.25, food_count=food_count
        )
        if len(scenario.foods) != food_count:
            continue
        plain = AntScenario(
            grid=scenario.grid, start=scenario.start, goal=scenario.goal, foods=frozenset()
        )
        plain_result = solve_bfs(plain)
        result = solve_bfs(scenario)
        if not plain_result.found or not result.found:
            continue
        assert result.cost >= plain_result.cost, "asking for more food must not lower the answer"
        compared += 1
    assert compared >= 5


# --------------------------------------------------------------------------
# A second greedy counterexample, on a symmetric map
# --------------------------------------------------------------------------


def test_nearest_food_first_loses_again_on_a_second_shape(
    assert_valid_solution: Callable[[AntScenario, SearchResult], None],
) -> None:
    """``. . . . . . G
    . F . . . . .
    . . . . . . .
    F . . . . . .

    ``(1, 0)`` is the only wall, so the two foods sit at 2 and 3 moves from the
    start. Nearest-first takes ``(1, 1)`` first and then has to come back down for
    ``(0, 3)``: ``2 + 3 + 9 = 14``. Going the other way round costs
    ``3 + 3 + 6 = 12``, and that is the answer, because the legs are
    ``d(S, (0, 3)) = 3``, ``d((0, 3), (1, 1)) = 3`` and ``d((1, 1), G) = 6``,
    which a route down column 0, back up column 1 and then along row 1 attains.
    """
    blocked = frozenset({Position(1, 0)})
    scenario = _scenario(7, 4, blocked, start=(0, 0), goal=(6, 0), foods=[(1, 1), (0, 3)])

    result = solve_bfs(scenario)

    assert_valid_solution(scenario, result)
    greedy = _greedy_nearest_food_cost(scenario)
    assert result.cost == 12
    assert greedy == 14
    assert result.path.index(Position(0, 3)) < result.path.index(Position(1, 1))
